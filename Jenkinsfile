pipeline {
  agent any

  options {
    timestamps()
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '20'))
    timeout(time: 60, unit: 'MINUTES')
  }

  parameters {
    choice(
      name: 'DEPLOY_ENV',
      choices: ['staging', 'production'],
      description: 'Target environment for deploy'
    )
    booleanParam(
      name: 'SKIP_DEPLOY',
      defaultValue: false,
      description: 'Build and test only — skip deploy stage'
    )
    booleanParam(
      name: 'FORCE_RECREATE',
      defaultValue: false,
      description: 'Force recreate containers on deploy'
    )
    booleanParam(
      name: 'RESET_POSTGRES',
      defaultValue: false,
      description: 'Delete Postgres data (users, documents, collections). Leave OFF so accounts survive deploys. Turn ON only if you need a fresh empty database.'
    )
    string(
      name: 'PUBLIC_API_URL',
      defaultValue: '',
      description: 'Browser-facing API URL baked into the web image. Leave empty to use same-origin /api via Nginx.'
    )
    string(
      name: 'ENV_CREDENTIAL_ID',
      defaultValue: 'doc-vault-env-file',
      description: 'Jenkins Secret file credential ID (only used when USE_ENV_CREDENTIAL=true)'
    )
    booleanParam(
      name: 'USE_ENV_CREDENTIAL',
      defaultValue: false,
      description: 'OFF by default. Turn ON only after you create the Jenkins Secret file credential.'
    )
    booleanParam(
      name: 'USE_REPO_ENV_EXAMPLE',
      defaultValue: true,
      description: 'Use doc-vault.env from the repo when no credential is loaded'
    )
  }

  environment {
    APP_NAME             = 'docvault'
    API_IMAGE            = "docvault-api:${env.BUILD_NUMBER}"
    API_IMAGE_LATEST     = 'docvault-api:latest'
    WEB_IMAGE            = "docvault-web:${env.BUILD_NUMBER}"
    WEB_IMAGE_LATEST     = 'docvault-web:latest'
    NGINX_IMAGE          = "docvault-nginx:${env.BUILD_NUMBER}"
    NGINX_IMAGE_LATEST   = 'docvault-nginx:latest'
    COMPOSE_PROJECT_NAME = 'docvault'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
        sh '''
          echo "Branch: ${GIT_BRANCH:-unknown}"
          echo "Commit: ${GIT_COMMIT:-unknown}"
          git rev-parse --short HEAD || true
          echo "=== Workspace files ==="
          ls -la
          test -f docker-compose.yml || { echo "ERROR: docker-compose.yml missing"; exit 1; }
          test -f docker/backend/Dockerfile || { echo "ERROR: docker/backend/Dockerfile missing"; exit 1; }
          test -f docker/frontend/Dockerfile || { echo "ERROR: docker/frontend/Dockerfile missing"; exit 1; }
          test -f docker/nginx/Dockerfile || { echo "ERROR: docker/nginx/Dockerfile missing"; exit 1; }
          test -f nginx/nginx.conf || { echo "ERROR: nginx/nginx.conf missing"; exit 1; }
          test -f backend/requirements.txt || { echo "ERROR: backend/requirements.txt missing"; exit 1; }
          test -f backend/scripts/jenkins_smoke.py || { echo "ERROR: jenkins_smoke.py missing"; exit 1; }
          test -f scripts/normalize_deploy_env.py || { echo "ERROR: normalize_deploy_env.py missing"; exit 1; }
          echo "=== frontend ==="
          ls -la frontend || true
          test -f frontend/package.json || { echo "ERROR: frontend/package.json missing — frontend source was not in git"; exit 1; }
          test -f frontend/package-lock.json || { echo "ERROR: frontend/package-lock.json missing"; exit 1; }
        '''
      }
    }

    stage('Detect Tools') {
      steps {
        sh '''
          echo "=== Agent tools ==="
          docker --version
          docker compose version
          echo "WORKSPACE=${WORKSPACE}"
          echo "PWD=$(pwd)"
        '''
      }
    }

    stage('Prepare Env') {
      steps {
        script {
          def usedEnv = false
          def credentialId = params.ENV_CREDENTIAL_ID?.trim() ?: 'doc-vault-env-file'

          if (params.USE_ENV_CREDENTIAL) {
            try {
              withCredentials([file(credentialsId: credentialId, variable: 'ENV_FILE')]) {
                sh '''
                  echo "Secret file path bound: $ENV_FILE"
                  test -f "$ENV_FILE" || { echo "ERROR: credential file path missing"; exit 1; }
                  cp -f "$ENV_FILE" .env.deploy
                  echo "Copied secret file → .env.deploy"
                '''
                usedEnv = true
              }
            } catch (err) {
              echo "Could not load credential ${credentialId}: ${err}"
              echo "Check: Manage Jenkins → Credentials → ID is exactly ${credentialId} (Secret file), scope Global, accessible to this job."
            }
          }

          if (!usedEnv) {
            sh '''
              echo "=== Looking for fallback env files ==="
              ls -la doc-vault.env .env /var/jenkins_home/doc-vault.env /var/jenkins_home/secrets/doc-vault.env 2>/dev/null || true
            '''
            def candidates = [
              '/var/jenkins_home/secrets/doc-vault.env',
              '/var/jenkins_home/doc-vault.env',
              'doc-vault.env',
              '.env',
            ]
            for (p in candidates) {
              if (fileExists(p)) {
                if (p == 'doc-vault.env' && !params.USE_REPO_ENV_EXAMPLE) {
                  echo "Skipping repo doc-vault.env because USE_REPO_ENV_EXAMPLE=false"
                  continue
                }
                sh "cp -f '${p}' .env.deploy"
                usedEnv = true
                echo "Using env file: ${p} → .env.deploy"
                break
              }
            }
          }

          if (!usedEnv) {
            error('''No env source found.
Create Jenkins credential:
  Kind: Secret file
  ID: doc-vault-env-file
  Scope: Global
Or keep doc-vault.env in the repo and leave USE_REPO_ENV_EXAMPLE=true.
Then rebuild.''')
          }

          sh '''
            set -e
            python3 scripts/normalize_deploy_env.py .env.deploy
            if [ -n "$PUBLIC_API_URL" ]; then
              python3 scripts/normalize_deploy_env.py .env.deploy --public-api-url "$PUBLIC_API_URL"
            fi
            echo "=== DATABASE_URL from .env.deploy ==="
            grep DATABASE_URL .env.deploy || true
            echo "=== POSTGRES_PASSWORD from .env.deploy ==="
            grep POSTGRES_PASSWORD .env.deploy || true
            if grep -qE '^TWILIO_ACCOUNT_SID=.+' .env.deploy; then
              echo "Twilio SID: set (from env file or Jenkins Global properties)"
            else
              echo "Twilio SID: empty — set TWILIO_* in Jenkins Global properties or doc-vault.env"
            fi
          '''
          echo "Prepared .env.deploy for ${params.DEPLOY_ENV}"
        }
      }
    }

    stage('Clean') {
      when {
        expression { return !params.SKIP_DEPLOY }
      }
      steps {
        script {
          sh '''
            set +e
            echo "=== Stop previous DocVault containers ==="
            docker compose -f docker-compose.yml down --remove-orphans || true
            docker rm -f docvault-api docvault-web docvault-postgres docvault-redis docvault-celery-worker docvault-celery-beat docvault-nginx 2>/dev/null || true
            docker rmi -f docvault-api:latest docvault-web:latest docvault-nginx:latest 2>/dev/null || true
            echo "=== Remaining docvault images ==="
            docker images | grep docvault || echo none
            echo "=== Docker volumes ==="
            docker volume ls
          '''
          if (params.RESET_POSTGRES) {
            sh '''
              set +e
              echo "RESET_POSTGRES=true — deleting Postgres volume (this wipes users and documents)"
              docker volume rm -f docvault_postgres_data postgres_data 2>/dev/null || true
              echo "=== Docker volumes after Postgres reset ==="
              docker volume ls
            '''
          } else {
            echo "Keeping Postgres volume docvault_postgres_data so users and documents survive this deploy"
          }
        }
      }
    }

    stage('Docker Build') {
      steps {
        sh '''
          set -e
          set -a
          # shellcheck disable=SC1091
          . ./.env.deploy
          set +a

          echo "Building API image..."
          docker build --no-cache -t ${API_IMAGE} -t ${API_IMAGE_LATEST} -f docker/backend/Dockerfile .

          echo "Building Web image (NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL:-empty})..."
          docker build \
            --build-arg "NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL:-}" \
            --build-arg "NEXT_PUBLIC_APP_NAME=${NEXT_PUBLIC_APP_NAME:-DocVault}" \
            --build-arg "WEB_BUILD_ID=${BUILD_NUMBER}-${GIT_COMMIT:-unknown}" \
            -t ${WEB_IMAGE} -t ${WEB_IMAGE_LATEST} \
            -f docker/frontend/Dockerfile .

          echo "Building Nginx image..."
          docker build -t ${NGINX_IMAGE} -t ${NGINX_IMAGE_LATEST} -f docker/nginx/Dockerfile .

          docker images | grep docvault | head -n 20 || docker images | head -n 12
        '''
      }
    }

    stage('Smoke Test') {
      steps {
        sh '''
          set -e
          docker run --rm \
            -e PYTHONPATH=/app \
            -e SECRET_KEY=jenkins-smoke-secret-key \
            -e JWT_SECRET=jenkins-smoke-jwt-secret \
            -e ENCRYPTION_KEY=jenkins-smoke-encryption-key \
            -e APP_ENV=development \
            -e DEBUG=false \
            ${API_IMAGE} \
            python scripts/jenkins_smoke.py
        '''
      }
    }

    stage('Deploy') {
      when {
        expression { return !params.SKIP_DEPLOY }
      }
      steps {
        sh '''
          set -e
          export IMAGE_TAG=${BUILD_NUMBER}
          export API_IMAGE=docvault-api:${BUILD_NUMBER}
          export WEB_IMAGE=docvault-web:${BUILD_NUMBER}
          export NGINX_IMAGE=docvault-nginx:${BUILD_NUMBER}
          cp -f .env.deploy .env

          set -a
          # shellcheck disable=SC1091
          . ./.env
          set +a

          export API_HOST_PORT=${API_HOST_PORT:-8000}
          export WEB_HOST_PORT=${WEB_HOST_PORT:-8088}
          echo "Publishing Nginx on host port ${WEB_HOST_PORT}"

          echo "=== DATABASE_URL after bash source ==="
          echo "DATABASE_URL=${DATABASE_URL}"
          echo "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}"
          echo "=== .env file lines ==="
          grep DATABASE_URL .env || true
          grep POSTGRES_PASSWORD .env || true
          echo "=== docker compose resolved env ==="
          docker compose -f docker-compose.yml config | grep DATABASE_URL || true
          docker compose -f docker-compose.yml config | grep POSTGRES_PASSWORD || true

          echo "Freeing previous DocVault containers (if any)..."
          docker compose -f docker-compose.yml down --remove-orphans || true
          docker rm -f docvault-api docvault-web docvault-postgres docvault-redis docvault-celery-worker docvault-celery-beat docvault-nginx 2>/dev/null || true

          mkdir -p "${STORAGE_HOST_PATH:-/var/lib/docvault}"

          echo "Starting Postgres first..."
          docker compose -f docker-compose.yml up -d --no-build postgres

          echo "Waiting for Postgres..."
          PG_USER="${POSTGRES_USER:-docvault}"
          ready=0
          i=1
          while [ "$i" -le 30 ]; do
            if docker exec docvault-postgres pg_isready -U "$PG_USER" >/dev/null 2>&1; then
              echo "Postgres ready"
              ready=1
              break
            fi
            echo "attempt ${i}: postgres starting"
            i=$((i + 1))
            sleep 2
          done
          if [ "$ready" != "1" ]; then
            echo "Postgres did not become ready"
            docker compose -f docker-compose.yml logs postgres --tail=80
            exit 1
          fi

          echo "Starting Redis..."
          docker compose -f docker-compose.yml up -d --no-build redis
          i=1
          while [ "$i" -le 20 ]; do
            if docker exec docvault-redis redis-cli ping >/dev/null 2>&1; then
              echo "Redis ready"
              break
            fi
            echo "attempt ${i}: redis starting"
            i=$((i + 1))
            sleep 2
          done

          echo "Running database migrations..."
          docker compose -f docker-compose.yml run --rm --no-deps backend alembic upgrade head

          RECREATE=""
          if [ "${FORCE_RECREATE}" = "true" ]; then
            RECREATE="--force-recreate"
          fi

          echo "Starting API, web, Celery, and Nginx from the images just built..."
          docker compose -f docker-compose.yml up -d --no-build $RECREATE backend celery_worker celery_beat frontend nginx
          echo "=== docvault-api DATABASE_URL inside container ==="
          docker exec docvault-api printenv DATABASE_URL || true
          echo "=== docvault-postgres POSTGRES_PASSWORD inside container ==="
          docker exec docvault-postgres printenv POSTGRES_PASSWORD || true

          echo "Waiting for API healthy via docker exec..."
          i=1
          while [ "$i" -le 45 ]; do
            if docker exec docvault-api curl -fsS http://127.0.0.1:8000/api/v1/health >/tmp/docvault_health.json 2>/dev/null; then
              echo "API healthy"
              cat /tmp/docvault_health.json
              echo
              docker compose -f docker-compose.yml ps
              exit 0
            fi
            STATUS="$(docker inspect -f '{{.State.Health.Status}}' docvault-api 2>/dev/null || echo unknown)"
            echo "attempt ${i}: health=${STATUS}"
            if [ "$STATUS" = "healthy" ]; then
              docker exec docvault-api curl -fsS http://127.0.0.1:8000/api/v1/health || true
              echo
              exit 0
            fi
            i=$((i + 1))
            sleep 3
          done
          echo "API health check failed"
          docker compose -f docker-compose.yml ps || true
          docker compose -f docker-compose.yml logs --tail=120
          exit 1
        '''
      }
    }

    stage('Post-Deploy Check') {
      when {
        expression { return !params.SKIP_DEPLOY }
      }
      steps {
        sh '''
          set -e
          echo "=== Container status ==="
          docker compose -f docker-compose.yml ps || true
          echo "=== API health (docker exec) ==="
          docker exec docvault-api curl -fsS http://127.0.0.1:8000/api/v1/health
          echo
          echo "=== Nginx /api/v1/health ==="
          docker exec docvault-nginx wget -qO- http://127.0.0.1/api/v1/health || true
          echo
          echo "=== Web responds ==="
          docker exec docvault-nginx wget -qO- http://127.0.0.1/ >/tmp/docvault_web.html 2>/dev/null || true
          if [ -s /tmp/docvault_web.html ]; then
            echo "web_ok bytes=$(wc -c </tmp/docvault_web.html)"
          else
            echo "WARN: could not fetch web HTML via nginx (image may still be starting)"
            docker logs docvault-web --tail=40 || true
            docker logs docvault-nginx --tail=40 || true
          fi
        '''
      }
    }
  }

  post {
    success {
      echo "DocVault ${params.DEPLOY_ENV} build #${env.BUILD_NUMBER} succeeded"
      echo "UI (Nginx): host port WEB_HOST_PORT (default 80)"
      echo "API is reached via Nginx /api; Postgres and Redis stay on the Docker network"
    }
    failure {
      echo "DocVault build #${env.BUILD_NUMBER} failed — check stage logs"
      sh 'docker compose -f docker-compose.yml logs --tail=120 || true'
    }
    always {
      sh 'rm -f .env.deploy.bak || true'
    }
  }
}
