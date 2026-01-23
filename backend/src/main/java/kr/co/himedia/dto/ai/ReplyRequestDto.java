package kr.co.himedia.dto.ai;

import lombok.*;

/**
 * 사용자의 추가 답변을 받기 위한 DTO
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ReplyRequestDto {
    private String userResponse; // 사용자의 텍스트 답변
}
