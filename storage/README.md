Original documents are stored here in development (`STORAGE_ROOT=./storage/data`).

Production Hostinger path:

```
/var/lib/docvault/
  users/
    {user_id}/
      documents/
      thumbnails/
      previews/
      encrypted/
      temp/
```

This directory must never be exposed by Nginx or the Next.js server. Access files only through authenticated FastAPI endpoints.
