package kr.co.himedia.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "dtc_codes")
@IdClass(DtcCodeId.class)
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class DtcCode {

    @Id
    @Column(length = 20)
    private String code;

    @Id
    @Column(length = 50)
    private String manufacturer;

    @Column(name = "description_ko", columnDefinition = "TEXT")
    private String descriptionKo;

    @Column(name = "description_en", columnDefinition = "TEXT")
    private String descriptionEn;

    @Column(name = "summary_ko", columnDefinition = "TEXT")
    private String summaryKo;

    @Column(name = "summary_en", columnDefinition = "TEXT")
    private String summaryEn;

    @Column(name = "tts_phrase", columnDefinition = "TEXT")
    private String ttsPhrase;

    @Column(name = "created_at", insertable = false, updatable = false)
    private LocalDateTime createdAt;
}
