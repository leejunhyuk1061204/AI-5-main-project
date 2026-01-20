import paramiko
import time

def connect_to_runpod(hostname, port, key_filepath, username='root'):
    """
    RunPod 서버에 SSH로 접속하여 간단한 테스트를 수행하는 함수
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"🔄 [연결 시도] {hostname}:{port}에 접속 중...")
        
        # SSH 키를 이용해 접속 (RunPod은 보통 SSH 키 방식 사용)
        # 키 파일 경로가 정확한지 꼭 확인해주세요!
        k = paramiko.RSAKey.from_private_key_file(key_filepath)
        
        client.connect(hostname, port=port, username=username, pkey=k)
        
        print("✅ [연결 성공] 서버에 접속되었습니다!")

        # 테스트 명령어: GPU 정보 확인 (nvidia-smi)
        # GPU가 없는 인스턴스라면 'ls -la' 등으로 바꿔서 테스트하세요.
        stdin, stdout, stderr = client.exec_command('nvidia-smi')
        
        output = stdout.read().decode()
        error = stderr.read().decode()

        if output:
            print("\n🖥️ [서버 응답 - GPU 상태]:")
            print(output)
        if error:
            print(f"⚠️ [에러]: {error}")

    except Exception as e:
        print(f"❌ [연결 실패]: {e}")
    finally:
        client.close()
        print("🔒 [연결 종료] 세션을 닫았습니다.")

if __name__ == "__main__":
    # ==========================================
    # 👇 [서버 켤 때마다 여기만 수정해서 실행하세요]
    # ==========================================
    HOST_IP = '123.456.789.0'    # RunPod에서 받은 IP (예: 192.168.1.5)
    PORT = 12345                 # RunPod에서 받은 Port (예: 30123)
    KEY_PATH = './my_key'        # 내 컴퓨터의 SSH 키 파일 경로 (윈도우/맥 경로 확인 필수)
    # ==========================================

    connect_to_runpod(HOST_IP, PORT, KEY_PATH)