# 스왑 메모리(Swap Memory) 설정 가이드

## 1. 스왑 메모리란?

스왑 메모리는 물리적인 RAM(메모리)이 부족할 때, **하드디스크(SSD/HDD)의 일부 공간을 RAM처럼 사용**하는 기술입니다.

### 비유: 책상과 서랍
- **RAM (책상)**: 당장 작업 중인 서류를 펼쳐놓는 공간. 빠르지만 좁습니다.
- **하드디스크 (서랍)**: 보관 중인 서류를 넣어두는 공간. 넓지만 꺼내려면 시간이 걸립니다.
- **스왑 (Swap)**: 책상이 꽉 찼을 때, 당장 안 보는 서류를 잠시 서랍 맨 위에 올려두는 것과 같습니다. 필요하면 다시 책상으로 가져옵니다.

### 장점
- **시스템 안정성**: 메모리 부족으로 프로그램이 강제 종료(OOM Killer)되는 것을 막아줍니다.
- **비용 절감**: 비싼 RAM을 추가하지 않고도 더 많은 프로그램을 실행할 수 있습니다.

### 단점
- **속도**: 하드디스크는 RAM보다 훨씬 느리기 때문에, 스왑을 너무 자주 사용하면 시스템 전체 속도가 느려질 수 있습니다.

---

## 2. 설정 방법 (Linux / EC2 기준)

서버(EC2) 터미널에 접속하여 아래 명령어들을 순서대로 입력하세요.
(일반적으로 RAM 1GB 인스턴스에는 **2GB** 스왑 파일을 권장합니다.)

### 1단계: 현재 메모리 상태 확인
```bash
free -h
```
*`Swap` 항목이 `0B`라면 설정이 안 된 상태입니다.*

### 2단계: 스왑 파일 생성 (2GB)
```bash
sudo fallocate -l 2G /swapfile
```
*(만약 `fallocate failed: Operation not supported` 에러가 나면 아래 명령어를 쓰세요)*
```bash
sudo dd if=/dev/zero of=/swapfile bs=128M count=16
```

### 3단계: 권한 설정 (보안)
루트 사용자만 읽고 쓸 수 있도록 권한을 수정합니다.
```bash
sudo chmod 600 /swapfile
```

### 4단계: 스왑 공간으로 변환
```bash
sudo mkswap /swapfile
```

### 5단계: 스왑 활성화
```bash
sudo swapon /swapfile
```

### 6단계: 재부팅 후에도 유지되도록 설정
서버를 껐다 켜도 설정이 풀리지 않게 `/etc/fstab` 파일을 수정합니다.
```bash
echo '/swapfile swap swap defaults 0 0' | sudo tee -a /etc/fstab
```

---

## 3. 설정 확인

다시 한 번 메모리를 확인하여 `Swap` 영역이 늘어났는지 봅니다.
```bash
free -h
```
결과 예시:
```
               total        used        free      shared  buff/cache   available
Mem:           966Mi       245Mi       123Mi       0.0Ki       597Mi       568Mi
Swap:          2.0Gi          0B       2.0Gi
```
**Swap: 2.0Gi** 가 보이면 성공입니다!
