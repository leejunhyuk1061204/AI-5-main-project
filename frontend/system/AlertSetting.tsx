import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Switch } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';

export default function AlertSetting() {
    const navigation = useNavigation<any>();

    // Mock state for switches
    const [maintenanceAlert, setMaintenanceAlert] = useState(true);
    const [aiAlert, setAiAlert] = useState(true);
    const [recallAlert, setRecallAlert] = useState(true);
    const [marketingAlert, setMarketingAlert] = useState(false);

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
        <View className="flex-row items-center justify-between p-4 mb-3 rounded-2xl bg-[#ffffff08] border border-[#ffffff0d]">
            <View className="flex-row items-center flex-1 gap-4">
                <View className="w-12 h-12 rounded-xl bg-[#1A1C24] border border-white/5 items-center justify-center shrink-0">
                    {iconType === 'material' ? (
                        <MaterialIcons name={icon} size={24} color={value ? "#007AFF" : "#6b7280"} />
                    ) : (
                        <MaterialCommunityIcons name={icon} size={24} color={value ? "#007AFF" : "#6b7280"} />
                    )}
                </View>
                <View className="flex-1">
                    <Text className="text-base font-semibold text-white mb-0.5">{title}</Text>
                    <Text className="text-sm font-normal text-white/40">{subtitle}</Text>
                </View>
            </View>
            <Switch
                trackColor={{ false: '#3f3f46', true: '#007AFF' }}
                thumbColor={'#ffffff'}
                ios_backgroundColor="#3f3f46"
                onValueChange={onValueChange}
                value={value}
                style={{ transform: [{ scaleX: 0.9 }, { scaleY: 0.9 }] }}
            />
        </View>
    );

    return (
        <View className="flex-1 bg-[#050505]">
            <StatusBar style="light" />
            <SafeAreaView className="flex-1" edges={['top']}>
                {/* Header */}
                <View className="flex-row items-center px-4 py-2 mb-4">
                    <TouchableOpacity
                        onPress={() => navigation.goBack()}
                        className="w-10 h-10 items-center justify-center -ml-2"
                    >
                        <MaterialIcons name="arrow-back-ios" size={20} color="white" />
                    </TouchableOpacity>
                    <Text className="flex-1 text-lg font-bold text-center text-white mr-8">
                        푸시 알림 수신 설정
                    </Text>
                </View>

                <ScrollView className="flex-1 px-4" showsVerticalScrollIndicator={false}>
                    {/* Section 1: Vehicle Management */}
                    <View className="mb-8">
                        <Text className="px-1 pb-4 text-sm font-semibold tracking-wider text-white/60">
                            차량 관리 서비스 알림
                        </Text>

                        <NotificationItem
                            icon="build"
                            title="정비 및 소모품 알림"
                            subtitle="교체 주기 및 정비 예약 알림"
                            value={maintenanceAlert}
                            onValueChange={setMaintenanceAlert}
                        />

                        <NotificationItem
                            icon="robot"
                            iconType="community"
                            title="AI 실시간 이상감지"
                            subtitle="엔진 분석 실시간 상태 이상 알림"
                            value={aiAlert}
                            onValueChange={setAiAlert}
                        />

                        <NotificationItem
                            icon="error-outline"
                            title="리콜 및 정기검사 정보"
                            subtitle="국토부 리콜 및 정기검사 일정"
                            value={recallAlert}
                            onValueChange={setRecallAlert}
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
                            value={marketingAlert}
                            onValueChange={setMarketingAlert}
                        />
                    </View>

                    {/* Footer Info */}
                    <View className="p-4 mb-12 border bg-black/40 rounded-2xl border-white/5">
                        <View className="flex-row items-start gap-3">
                            <MaterialIcons name="info-outline" size={20} color="#007AFF" />
                            <Text className="flex-1 text-xs leading-relaxed font-normal text-white/50">
                                차량 안전과 직결된 긴급 경보 및 시스템 필수 공지사항은 설정과 관계없이 발송될 수 있습니다. AI 이상감지 알림은 데이터 연결 상태에 따라 실제 차량 상태와 다를 수 있습니다.
                            </Text>
                        </View>
                    </View>
                </ScrollView>
            </SafeAreaView>
        </View>
    );
}
