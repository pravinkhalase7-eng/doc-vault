from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentMetadata
from app.models.entity import Entity, EntityRelationship
from app.models.enums import EntityKind, RelationshipType


async def upsert_from_document(db: AsyncSession, doc: Document) -> None:
    if doc.related_person:
        await _ensure_entity(db, doc.user_id, EntityKind.PERSON, doc.related_person)
    fields = (
        await db.scalars(select(DocumentMetadata).where(DocumentMetadata.document_id == doc.id))
    ).all()
    by_name = {f.field_name: f.value for f in fields if f.value}
    if by_name.get("vehicle_number"):
        vehicle = await _ensure_entity(db, doc.user_id, EntityKind.VEHICLE, by_name["vehicle_number"])
        owner = await _ensure_entity(db, doc.user_id, EntityKind.PERSON, doc.related_person or "Me")
        await _ensure_rel(db, doc.user_id, owner.id, vehicle.id, RelationshipType.OWNS, doc.id)
    if by_name.get("policy_number"):
        policy = await _ensure_entity(db, doc.user_id, EntityKind.POLICY, by_name["policy_number"])
        owner = await _ensure_entity(db, doc.user_id, EntityKind.PERSON, doc.related_person or "Me")
        await _ensure_rel(db, doc.user_id, owner.id, policy.id, RelationshipType.OWNS, doc.id)


async def _ensure_entity(db: AsyncSession, user_id: str, kind: EntityKind, name: str) -> Entity:
    entity = await db.scalar(
        select(Entity).where(Entity.user_id == user_id, Entity.kind == kind, Entity.name == name)
    )
    if entity:
        return entity
    entity = Entity(user_id=user_id, kind=kind, name=name)
    db.add(entity)
    await db.flush()
    return entity


async def _ensure_rel(
    db: AsyncSession, user_id: str, from_id: str, to_id: str, relation: RelationshipType, document_id: str
) -> None:
    existing = await db.scalar(
        select(EntityRelationship).where(
            EntityRelationship.user_id == user_id,
            EntityRelationship.from_entity_id == from_id,
            EntityRelationship.to_entity_id == to_id,
            EntityRelationship.relation == relation,
        )
    )
    if existing:
        return
    db.add(
        EntityRelationship(
            user_id=user_id,
            from_entity_id=from_id,
            to_entity_id=to_id,
            relation=relation,
            document_id=document_id,
        )
    )


async def graph_for_user(db: AsyncSession, user_id: str) -> dict:
    entities = (await db.scalars(select(Entity).where(Entity.user_id == user_id))).all()
    rels = (await db.scalars(select(EntityRelationship).where(EntityRelationship.user_id == user_id))).all()
    return {
        "entities": [{"id": e.id, "kind": e.kind.value, "name": e.name} for e in entities],
        "relationships": [
            {
                "from": r.from_entity_id,
                "to": r.to_entity_id,
                "relation": r.relation.value,
                "document_id": r.document_id,
            }
            for r in rels
        ],
    }
