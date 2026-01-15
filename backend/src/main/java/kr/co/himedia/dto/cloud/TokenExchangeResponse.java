package kr.co.himedia.dto.cloud;

import lombok.Data;

@Data
public class TokenExchangeResponse {
    private String access_token;
    private String refresh_token;
    private long expires_in;
    private String token_type;
}
