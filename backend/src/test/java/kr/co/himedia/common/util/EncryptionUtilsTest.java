package kr.co.himedia.common.util;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import static org.assertj.core.api.Assertions.assertThat;

class EncryptionUtilsTest {

    private EncryptionUtils encryptionUtils;

    @BeforeEach
    void setUp() {
        encryptionUtils = new EncryptionUtils();
        ReflectionTestUtils.setField(encryptionUtils, "secretKey", "test-secret-key-32-bytes-secure!!!");
    }

    @Test
    @DisplayName("문자열을 암호화하고 다시 복호화하면 원래 문자열이 나와야 한다.")
    void encryptAndDecrypt_shouldReturnOriginalString() {
        // given
        String originalText = "smartcar_secret_token_12345";

        // when
        String encryptedText = encryptionUtils.encrypt(originalText);
        String decryptedText = encryptionUtils.decrypt(encryptedText);

        // then
        assertThat(encryptedText).isNotEqualTo(originalText);
        assertThat(decryptedText).isEqualTo(originalText);
    }

    @Test
    @DisplayName("서로 다른 암호화 결과는 IV로 인해 매번 달라야 한다.")
    void encrypt_shouldProduceDifferentResultsForEachCall() {
        // given
        String originalText = "same_text";

        // when
        String encrypted1 = encryptionUtils.encrypt(originalText);
        String encrypted2 = encryptionUtils.encrypt(originalText);

        // then
        assertThat(encrypted1).isNotEqualTo(encrypted2);
        assertThat(encryptionUtils.decrypt(encrypted1)).isEqualTo(originalText);
        assertThat(encryptionUtils.decrypt(encrypted2)).isEqualTo(originalText);
    }
}
