package kr.co.himedia.dto.user;

import kr.co.himedia.entity.UserSetting;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class UserSettingResponse {

    private boolean notiMaintenance;
    private boolean notiAnomaly;
    private boolean notiDtcTts;
    private boolean notiMarketing;
    private boolean nightPushAllowed;

    public static UserSettingResponse from(UserSetting setting) {
        return UserSettingResponse.builder()
                .notiMaintenance(setting.getNotiMaintenance())
                .notiAnomaly(setting.getNotiAnomaly())
                .notiDtcTts(setting.getNotiDtcTts())
                .notiMarketing(setting.getNotiMarketing())
                .nightPushAllowed(setting.getNightPushAllowed())
                .build();
    }
}
