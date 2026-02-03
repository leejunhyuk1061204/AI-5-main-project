import React, { useState, useEffect } from 'react';
import { View, Text, Modal, TouchableOpacity, Switch, StyleSheet, ActivityIndicator, Dimensions } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { getUserSettings, updateUserSettings, UserSetting } from '../api/userSettingApi';
import { BlurView } from 'expo-blur';

interface Props {
    visible: boolean;
    onClose: () => void;
}

const { width } = Dimensions.get('window');

export default function NotificationOnboardingModal({ visible, onClose }: Props) {
    const [loading, setLoading] = useState(true);
    const [settings, setSettings] = useState<UserSetting>({
        notiMaintenance: true,
        notiAnomaly: true,
        notiDtcTts: true,
        notiMarketing: false,
        nightPushAllowed: false
    });

    useEffect(() => {
        if (visible) {
            loadSettings();
        }
    }, [visible]);

    const loadSettings = async () => {
        try {
            setLoading(true);
            const data = await getUserSettings();
            setSettings(data);
        } catch (error) {
            console.error('Failed to load settings:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleToggle = async (key: keyof UserSetting, value: boolean) => {
        // Optimistic update
        setSettings(prev => ({ ...prev, [key]: value }));
        try {
            await updateUserSettings({ [key]: value });
        } catch (error) {
            console.error('Failed to update setting:', error);
            // Revert silently or handle error? For onboarding, silent is often better UX
        }
    };

    const handleComplete = () => {
        onClose();
    };

    const SwitchItem = ({ label, subLabel, value, onChange }: any) => (
        <View style={styles.itemContainer}>
            <View style={{ flex: 1 }}>
                <Text style={styles.itemLabel}>{label}</Text>
                <Text style={styles.itemSubLabel}>{subLabel}</Text>
            </View>
            <Switch
                trackColor={{ false: '#3f3f46', true: '#0d7ff2' }}
                thumbColor={'#ffffff'}
                ios_backgroundColor="#3f3f46"
                onValueChange={onChange}
                value={value}
                style={{ transform: [{ scaleX: 0.8 }, { scaleY: 0.8 }] }}
            />
        </View>
    );

    return (
        <Modal
            visible={visible}
            transparent={true}
            animationType="fade"
            onRequestClose={() => { }} // Block back button closing? Or allow?
        >
            <View style={styles.overlay}>
                <View style={styles.container}>
                    {/* Header Icon */}
                    <View style={styles.iconContainer}>
                        <LinearGradient
                            colors={['rgba(13, 127, 242, 0.2)', 'rgba(6, 182, 212, 0.1)']}
                            style={styles.iconGradient}
                        >
                            <MaterialIcons name="notifications-active" size={32} color="#0d7ff2" />
                        </LinearGradient>
                    </View>

                    <Text style={styles.title}>알림 설정 안내</Text>
                    <Text style={styles.description}>
                        차량의 상태와 주요 정보를 놓치지 않도록{'\n'}알림을 설정해보세요.
                    </Text>

                    {loading ? (
                        <View style={{ height: 200, justifyContent: 'center' }}>
                            <ActivityIndicator color="#0d7ff2" />
                        </View>
                    ) : (
                        <View style={styles.content}>
                            <SwitchItem
                                label="정비 및 소모품 알림"
                                subLabel="교체 주기 및 정비 예약 알림"
                                value={settings.notiMaintenance}
                                onChange={(v: boolean) => handleToggle('notiMaintenance', v)}
                            />
                            <SwitchItem
                                label="AI 진단 리포트 알림"
                                subLabel="매 주행 후 AI 분석 리포트 발송"
                                value={settings.notiAnomaly}
                                onChange={(v: boolean) => handleToggle('notiAnomaly', v)}
                            />
                            <SwitchItem
                                label="고장 발생 시 음성 안내"
                                subLabel="위험 감지 시 즉시 음성 경고"
                                value={settings.notiDtcTts}
                                onChange={(v: boolean) => handleToggle('notiDtcTts', v)}
                            />
                            <SwitchItem
                                label="야간 푸시 알림"
                                subLabel="21:00 ~ 08:00 알림 수신 허용"
                                value={settings.nightPushAllowed}
                                onChange={(v: boolean) => handleToggle('nightPushAllowed', v)}
                            />
                            <SwitchItem
                                label="마케팅 정보 수신"
                                subLabel="이벤트 및 혜택 알림"
                                value={settings.notiMarketing}
                                onChange={(v: boolean) => handleToggle('notiMarketing', v)}
                            />
                        </View>
                    )}

                    <TouchableOpacity
                        style={styles.buttonWrapper}
                        onPress={handleComplete}
                        activeOpacity={0.9}
                    >
                        <LinearGradient
                            colors={['#0d7ff2', '#06b6d4']}
                            start={{ x: 0, y: 0 }}
                            end={{ x: 1, y: 0 }}
                            style={styles.gradientButton}
                        >
                            <Text style={styles.buttonText}>설정 완료</Text>
                        </LinearGradient>
                    </TouchableOpacity>
                </View>
            </View>
        </Modal>
    );
}

const styles = StyleSheet.create({
    overlay: {
        flex: 1,
        backgroundColor: 'rgba(0,0,0,0.75)',
        justifyContent: 'center',
        alignItems: 'center',
        padding: 24,
    },
    container: {
        width: '100%',
        maxWidth: 340,
        backgroundColor: '#1e2936',
        borderRadius: 24,
        padding: 24,
        alignItems: 'center',
        borderWidth: 1,
        borderColor: 'rgba(255,255,255,0.1)',
        shadowColor: "#000",
        shadowOffset: { width: 0, height: 10 },
        shadowOpacity: 0.5,
        shadowRadius: 20,
        elevation: 10,
    },
    iconContainer: {
        marginBottom: 20,
    },
    iconGradient: {
        width: 64,
        height: 64,
        borderRadius: 32,
        alignItems: 'center',
        justifyContent: 'center',
        borderWidth: 1,
        borderColor: 'rgba(13, 127, 242, 0.3)',
    },
    title: {
        fontSize: 20,
        fontWeight: 'bold',
        color: 'white',
        marginBottom: 8,
    },
    description: {
        fontSize: 14,
        color: '#94a3b8',
        textAlign: 'center',
        lineHeight: 20,
        marginBottom: 24,
    },
    content: {
        width: '100%',
        gap: 12,
        marginBottom: 24,
    },
    itemContainer: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        backgroundColor: 'rgba(255,255,255,0.03)',
        padding: 16,
        borderRadius: 16,
        borderWidth: 1,
        borderColor: 'rgba(255,255,255,0.05)',
    },
    itemLabel: {
        color: 'white',
        fontSize: 15,
        fontWeight: '600',
        marginBottom: 2,
    },
    itemSubLabel: {
        color: '#64748b',
        fontSize: 11,
    },
    buttonWrapper: {
        width: '100%',
        height: 52,
        shadowColor: "rgba(13, 127, 242, 0.4)",
        shadowOffset: { width: 0, height: 0 },
        shadowOpacity: 1,
        shadowRadius: 10,
        elevation: 5,
    },
    gradientButton: {
        width: '100%',
        height: '100%',
        borderRadius: 26,
        alignItems: 'center',
        justifyContent: 'center',
    },
    buttonText: {
        color: 'white',
        fontSize: 16,
        fontWeight: 'bold',
    },
});
