# setup-volumes.ps1
# External 볼륨과 네트워크 생성 스크립트 - 처음에 한번만 실행

Write-Host "=== Library RAG System Setup ===" -ForegroundColor Green

# 1. 네트워크 생성
Write-Host "`n[1/4] Creating network..." -ForegroundColor Cyan
docker network create library-ragnet 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host " Network 'library-ragnet' created" -ForegroundColor Green
} else {
    Write-Host " Network 'library-ragnet' already exists" -ForegroundColor Yellow
}

# 2. etcd 볼륨 생성
Write-Host "`n[2/4] Creating etcd volume..." -ForegroundColor Cyan
docker volume create library_etcd_data 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host " Volume 'library_etcd_data' created" -ForegroundColor Green
} else {
    Write-Host "Volume 'library_etcd_data' already exists" -ForegroundColor Yellow
}

# 3. Milvus 볼륨 생성
Write-Host "`n[3/4] Creating Milvus volume..." -ForegroundColor Cyan
docker volume create library_milvus_data 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host " Volume 'library_milvus_data' created" -ForegroundColor Green
} else {
    Write-Host " Volume 'library_milvus_data' already exists" -ForegroundColor Yellow
}

# 4. MinIO 볼륨 생성
Write-Host "`n[4/4] Creating MinIO volume..." -ForegroundColor Cyan
docker volume create library_minio_data 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host " Volume 'library_minio_data' created" -ForegroundColor Green
} else {
    Write-Host " Volume 'library_minio_data' already exists" -ForegroundColor Yellow
}

# 5. 확인
Write-Host "`n=== Verification ===" -ForegroundColor Green
Write-Host "`nNetworks:" -ForegroundColor Cyan
docker network ls | Select-String -Pattern "library-ragnet"

Write-Host "`nVolumes:" -ForegroundColor Cyan
docker volume ls | Select-String -Pattern "library_"

Write-Host "`n Setup complete!" -ForegroundColor Green
Write-Host "`nNext step: cd docker && docker-compose up -d" -ForegroundColor Yellow