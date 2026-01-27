package kr.co.himedia.domain;

/**
 * AI가 사용자에게 요청하는 추가 액션 정의
 */
public enum DiagAction {
    ANSWER_TEXT, // 텍스트 답변 요청
    CAPTURE_PHOTO, // 사진 촬영 요청
    RECORD_AUDIO // 추가 음성 녹음 요청
}
