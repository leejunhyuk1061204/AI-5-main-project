package kr.co.himedia.dto.user;

import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class UserSettingRequest {

    private Boolean notiMaintenance;
    private Boolean notiAnomaly;
    private Boolean notiDtcTts;
    private Boolean notiMarketing;
    private Boolean nightPushAllowed;
}
