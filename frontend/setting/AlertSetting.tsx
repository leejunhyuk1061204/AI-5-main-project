import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, Switch, Modal, ActivityIndicator, Alert } from 'react-native';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import BaseScreen from '../components/layout/BaseScreen';
import { getUserSettings, updateUserSettings, UserSetting } from '../api/userSettingApi';

export default function AlertSetting() {
    const navigation = useNavigation<any>();
    const [loading, setLoading] = useState(true);

    // Default state
    const [settings, setSettings] = useState<UserSetting>({
        notiMaintenance: false,
        notiAnomaly: false,
        notiDtcTts: false,
        notiMarketing: false,
        nightPushAllowed: false
    });

    // Fetch settings on mount
    useEffect(() => {
        loadSettings();
    }, []);

    const loadSettings = async () => {
        try {
            setLoading(true);
            const data = await getUserSettings();
            setSettings(data);
        } catch (error) {
            console.error('Failed to load settings:', error);
            Alert.alert('오류', '설정 정보를 불러오는데 실패했습니다.');
        } finally {
            setLoading(false);
        }
    };

    const handleToggle = async (key: keyof UserSetting, value: boolean) => {
        // Optimistic update
        const previousSettings = { ...settings };
        setSettings(prev => ({ ...prev, [key]: value }));

        try {
            await updateUserSettings({ [key]: value });
        } catch (error) {
            console.error('Failed to update setting:', error);
            // Revert on failure
            setSettings(previousSettings);
            Alert.alert('오류', '설정 변경에 실패했습니다.');
        }
    };

    const NotificationItem = ({
        icon,
        title,
        subtitle,
        value,
        onValueChange,
        iconType = 'material'
    }: {
        icon: any;
        title: string;
        subtitle: string;
        value: boolean;
        onValueChange: (val: boolean) => void;
        iconType?: 'material' | 'community';
    }) => (
        <View className="flex-row items-center justify-between p-4 mb-3 rounded-2xl bg-white/5 border border-white/10">
            <View className="flex-row items-center flex-1 gap-4">
                <View className="w-12 h-12 rounded-xl bg-surface-dark border border-white/5 items-center justify-center shrink-0">
                    {iconType === 'material' ? (
                        <MaterialIcons name={icon} size={24} color={value ? "#0d7ff2" : "#6b7280"} />
                    ) : (
                        <MaterialCommunityIcons name={icon} size={24} color={value ? "#0d7ff2" : "#6b7280"} />
                    )}
                </View>
                <View className="flex-1">
                    <Text className="text-base font-semibold text-white mb-0.5">{title}</Text>
                    <Text className="text-sm font-normal text-white/40">{subtitle}</Text>
                </View>
            </View>
            <Switch
                trackColor={{ false: '#3f3f46', true: '#0d7ff2' }}
                thumbColor={'#ffffff'}
                ios_backgroundColor="#3f3f46"
                onValueChange={onValueChange}
                value={value}
                style={{ transform: [{ scaleX: 0.9 }, { scaleY: 0.9 }] }}
            />
        </View>
    );

    const HeaderCustom = (
        <View className="flex-row items-center px-4 py-2 mb-4 border-b border-white/5">
            <TouchableOpacity
                onPress={() => navigation.goBack()}
                className="w-10 h-10 items-center justify-center -ml-2"
            >
                <MaterialIcons name="arrow-back-ios" size={20} color="white" />
            </TouchableOpacity>
            <Text className="flex-1 text-lg font-bold text-center text-white mr-8">
                알림 수신 설정
            </Text>
        </View>
    );

    if (loading) {
        return (
            <BaseScreen header={HeaderCustom} padding={false}>
                <View className="flex-1 items-center justify-center">
                    <ActivityIndicator size="large" color="#0d7ff2" />
                </View>
            </BaseScreen>
        );
    }

    return (
        <BaseScreen
            header={HeaderCustom}
            scrollable={true}
            padding={false}
        >
            <View className="px-4">
                {/* Section 1: Vehicle Management */}
                <View className="mb-8">
                    <Text className="px-1 pb-4 text-sm font-semibold tracking-wider text-white/60">
                        차량 관리 서비스 알림
                    </Text>

                    <NotificationItem
                        icon="build"
                        title="정비 및 소모품 알림"
                        subtitle="교체 주기 및 정비 예약 알림"
                        value={settings.notiMaintenance}
                        onValueChange={(val) => handleToggle('notiMaintenance', val)}
                    />

                    <NotificationItem
                        icon="analytics"
                        title="AI 진단 리포트 알림"
                        subtitle="매 주행 후 AI 분석 리포트 발송"
                        value={settings.notiAnomaly}
                        onValueChange={(val) => handleToggle('notiAnomaly', val)}
                    />

                    <NotificationItem
                        icon="record-voice-over"
                        title="고장 발생 시 음성 안내"
                        subtitle="주행 중 문제 감지 시 즉시 음성 경고"
                        value={settings.notiDtcTts}
                        onValueChange={(val) => handleToggle('notiDtcTts', val)}
                    />

                    <NotificationItem
                        icon="nights-stay"
                        title="야간 푸시 알림"
                        subtitle="21:00 ~ 08:00 알림 수신 허용"
                        value={settings.nightPushAllowed}
                        onValueChange={(val) => handleToggle('nightPushAllowed', val)}
                    />
                </View>

                {/* Section 2: Marketing */}
                <View className="mb-8">
                    <Text className="px-1 pb-4 text-sm font-semibold tracking-wider text-white/60">
                        혜택 및 이벤트 알림
                    </Text>

                    <NotificationItem
                        icon="campaign"
                        title="마케팅 정보 수신"
                        subtitle="이벤트, 쿠폰 및 서비스 혜택 안내"
                        value={settings.notiMarketing}
                        onValueChange={(val) => handleToggle('notiMarketing', val)}
                    />
                </View>

                {/* Footer Info */}
                <View className="p-4 mb-12 border bg-black/40 rounded-2xl border-white/5">
                    <View className="flex-row items-start gap-3">
                        <MaterialIcons name="info-outline" size={20} color="#0d7ff2" />
                        <Text className="flex-1 text-xs leading-relaxed font-normal text-white/50">
                            차량 안전과 직결된 긴급 경보 및 시스템 필수 공지사항은 설정과 관계없이 발송될 수 있습니다.
                        </Text>
                    </View>
                </View>
            </View>
        </BaseScreen>
    );
}
