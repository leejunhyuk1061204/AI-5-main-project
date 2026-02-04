import api from './axios';

export interface UserSetting {
    notiMaintenance: boolean;
    notiAnomaly: boolean;
    notiDtcTts: boolean;
    notiMarketing: boolean;
    nightPushAllowed: boolean;
}

export interface UserSettingRequest {
    notiMaintenance?: boolean;
    notiAnomaly?: boolean;
    notiDtcTts?: boolean;
    notiMarketing?: boolean;
    nightPushAllowed?: boolean;
}

export const getUserSettings = async (): Promise<UserSetting> => {
    const response = await api.get('/api/v1/user/settings');
    return response.data.data;
};

export const updateUserSettings = async (data: UserSettingRequest): Promise<UserSetting> => {
    const response = await api.put('/api/v1/user/settings', data);
    return response.data.data;
};
