import os
from openai import OpenAI
from dotenv import load_dotenv

# ai/.env 파일 로드
load_dotenv("ai/.env")

def test_openai_key():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ 에러: OPENAI_API_KEY를 .env 파일에서 찾을 수 없습니다.")
        return

    client = OpenAI(api_key=api_key)
    
    try:
        # 아주 가벼운 요청으로 키 유효성 확인
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=5
        )
        print("✅ 성공: OpenAI API Key가 정상적으로 연결되었습니다!")
        print(f"응답 요약: {response.choices[0].message.content}")
    except Exception as e:
        print(f"❌ 실패: OpenAI API 호출 중 오류 발생: {e}")

if __name__ == "__main__":
    test_openai_key()
