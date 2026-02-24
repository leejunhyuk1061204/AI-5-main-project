import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ImageBackground, Dimensions, BackHandler } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { useRoute, RouteProp } from '@react-navigation/native';
import { StatusBar } from 'expo-status-bar';
import Animated, {
    useSharedValue,
    useAnimatedStyle,
    withRepeat,
    withTiming,
    withSequence,
    Easing
} from 'react-native-reanimated';

import { useAiDiagnosisStore, DiagType } from '../store/useAiDiagnosisStore';
import { useAlertStore } from '../store/useAlertStore';

const { width } = Dimensions.get('window');

type ActiveLoadingParams = {
    vehicleId?: string;
    sessionId?: string;
    diagType?: DiagType;
};

export default function ObdDiagLoading({ navigation }: any) {
    const insets = useSafeAreaInsets();
    const route = useRoute<RouteProp<{ ObdDiagLoading: ActiveLoadingParams }, 'ObdDiagLoading'>>();
    const vehicleId = route.params?.vehicleId;
    const diagType: DiagType = route.params?.diagType || 'OBD';
    const paramSessionId = route.params?.sessionId;

    const {
        sessions,
        connectSse,
        clearSseFailed,
        selectedVehicleId
    } = useAiDiagnosisStore();

    const session = sessions[diagType];
    const {
        currentSessionId,
        sseProgress,
        sseStatusMessage,
        sseFailedWithMessage,
        status,
        diagResult
    } = session;

    // store 반영이 비동기라 로딩 진입 직후 currentSessionId가 비어 있을 수 있음 → params.sessionId 사용
    const effectiveSessionId = currentSessionId || paramSessionId;

    const isComplete = status === 'REPORT' || status === 'INTERACTIVE' || status === 'ACTION_REQUIRED';
    const completeTarget = status === 'REPORT' ? '결과 화면' : '대화창';
    const [failedDisplay, setFailedDisplay] = useState(false);

    useEffect(() => {
        console.log('[ObdDiagLoading] mount/params', { diagType, vehicleId, paramSessionId, currentSessionId, effectiveSessionId });
    }, [diagType, vehicleId, paramSessionId, currentSessionId, effectiveSessionId]);

    // Animations
    const scanLineY = useSharedValue(0);
    const particleOpacity = useSharedValue(0.3);
    const rotate = useSharedValue(0);

    // Ensure SSE is connected when we have a session (no cleanup: connection lives in store)
    useEffect(() => {
        if (!effectiveSessionId) {
            console.log('[ObdDiagLoading] skip connectSse: no effectiveSessionId');
            return;
        }
        console.log('[ObdDiagLoading] connectSse', { diagType, effectiveSessionId });
        connectSse(diagType, effectiveSessionId);
    }, [effectiveSessionId, connectSse, diagType]);

    // INTERACTIVE → 채팅, REPORT → 리포트만 이동 (한 번에 하나만)
    useEffect(() => {
        const sid = effectiveSessionId;
        if (status === 'REPORT') {
            console.log('[ObdDiagLoading] status=REPORT, replace → DiagnosisReport');
            const t = setTimeout(() => {
                navigation.replace('DiagnosisReport', { reportData: diagResult, sessionId: sid, diagType });
            }, 800);
            return () => clearTimeout(t);
        }
        if (status === 'INTERACTIVE' || status === 'ACTION_REQUIRED') {
            console.log('[ObdDiagLoading] status=INTERACTIVE/ACTION_REQUIRED, replace → AiDiagChat');
            const t = setTimeout(() => {
                navigation.replace('AiDiagChat', { sessionId: sid, vehicleId: vehicleId ?? selectedVehicleId ?? undefined, diagType });
            }, 800);
            return () => clearTimeout(t);
        }
    }, [status, effectiveSessionId, vehicleId, selectedVehicleId, diagResult, navigation, diagType]);

    // 뒤로가기 시 항상 진단 메인(DiagTab)으로
    const goToDiagMain = () => {
        (navigation as any).navigate('MainPage', { screen: 'DiagTab' });
    };

    useEffect(() => {
        const sub = BackHandler.addEventListener('hardwareBackPress', () => {
            goToDiagMain();
            return true;
        });
        return () => sub.remove();
    }, [navigation]);

    // Show failure alert when SSE failed; 화면에 "진단 실패" 표시 후 알림
    useEffect(() => {
        if (!sseFailedWithMessage) return;
        const message = sseFailedWithMessage;
        setFailedDisplay(true);
        clearSseFailed(diagType);
        useAlertStore.getState().showAlert('진단 실패', message, 'ERROR', goToDiagMain);
    }, [sseFailedWithMessage, clearSseFailed, diagType]);

    // Animations start on mount
    useEffect(() => {
        scanLineY.value = withRepeat(
            withTiming(1, { duration: 3000, easing: Easing.linear }),
            -1,
            true
        );
        particleOpacity.value = withRepeat(
            withSequence(
                withTiming(1, { duration: 800 }),
                withTiming(0.3, { duration: 800 })
            ),
            -1,
            true
        );
        rotate.value = withRepeat(
            withTiming(360, { duration: 20000, easing: Easing.linear }),
            -1,
            false
        );
    }, []);

    const animatedScanLineStyle = useAnimatedStyle(() => ({
        top: `${scanLineY.value * 100}%`,
    }));

    const animatedParticleStyle = useAnimatedStyle(() => ({
        opacity: particleOpacity.value,
    }));

    const animatedRotateStyle = useAnimatedStyle(() => ({
        transform: [{ rotate: `${rotate.value}deg` }],
    }));

    // Reusable Status Item
    const StatusItem = ({ icon, label, status, isWaiting = false, isLast = false }: { icon: keyof typeof MaterialIcons.glyphMap, label: string, status: string, isWaiting?: boolean, isLast?: boolean }) => (
        <View className={`flex-1 bg-white/5 border border-white/5 rounded-lg p-3 flex-row items-center gap-3 ${isWaiting ? 'opacity-50' : ''}`}>
            <View className={`w-8 h-8 rounded-full items-center justify-center shrink-0 ${isWaiting ? 'bg-white/5' : 'bg-primary/10'}`}>
                <MaterialIcons
                    name={icon}
                    size={18}
                    color={isWaiting ? '#94a3b8' : '#0d7ff2'}
                />
            </View>
            <View>
                <Text className="text-[10px] uppercase tracking-wider text-slate-400 mb-0.5">{label}</Text>
                <Text className={`text-xs font-bold ${isWaiting ? 'text-slate-400' : 'text-white'}`}>
                    {status}
                </Text>
            </View>
        </View>
    );

    return (
        <View className="flex-1 bg-background-dark">
            <SafeAreaView className="flex-1" edges={['top', 'left', 'right', 'bottom']}>
            <StatusBar style="light" />

            {/* Header — 상단 safe area 반영 */}
            <View className="z-10 bg-transparent absolute top-0 w-full" style={{ paddingTop: insets.top }}>
                <View className="flex-row items-center justify-between px-4 py-3">
                    <TouchableOpacity
                        onPress={goToDiagMain}
                        className="w-10 h-10 items-center justify-center -ml-2"
                    >
                        <MaterialIcons name="arrow-back-ios-new" size={24} color="#0d7ff2" />
                    </TouchableOpacity>
                    <Text className="text-white text-lg font-bold tracking-tight uppercase opacity-90 pr-8 flex-1 text-center">
                        AI Diagnostics
                    </Text>
                    <View className="w-10" />
                </View>
            </View>

            {/* Main Content - paddingTop so car image is not covered by header */}
            <View
                className="flex-1 items-center justify-center px-6 pb-8"
                style={{ paddingTop: insets.top + 48 }}
            >

                {/* Central Visual: Holographic Car Scanner */}
                <View className="relative w-full aspect-square max-h-[360px] mb-8 items-center justify-center">



                    {/* Rotating Hexagon Pattern (Decorative Ring) */}
                    <Animated.View
                        style={[
                            animatedRotateStyle,
                            {
                                position: 'absolute', width: '100%', height: '100%',
                                borderRadius: 999, borderWidth: 1, borderColor: 'rgba(13,127,242,0.1)',
                                borderStyle: 'dashed'
                            }
                        ]}
                    />

                    {/* Main Hologram Image */}
                    <View className="w-full h-full relative z-10 overflow-hidden rounded-2xl">
                        <ImageBackground
                            source={{ uri: "https://lh3.googleusercontent.com/aida-public/AB6AXuBrbOpEDKXATHlLHpS3GcTwAzp_yKQDUm98m3S6dgStGdY9E9FbyxKJJEcIqX2JHARPzYLv3bwASRstoXUZTtKfxD7U51lwMEdoIZGgp7pRrPwrPILsPnUWSQ10odw_FXea7qH_wmlGTvVzeVHM7YgChicjH6yEGbfqhaCWuHKe9H-KdUQMZjKtYH1pNsmvPt9VFVsEdSqbS4R9CDAGlskDuKfCc2hhTHJe1Iiv_ztmrHSowk1B7NsidsymB4KRl4PEJcJjokCar12y" }}
                            className="w-full h-full"
                            resizeMode="contain"
                            style={{ opacity: 0.9 }}
                        >
                            {/* Overlay to make it blueish */}
                            <View className="absolute inset-0 bg-[#101922]/40" />
                        </ImageBackground>

                        {/* Scanner Line */}
                        <Animated.View
                            style={[
                                animatedScanLineStyle,
                                {
                                    position: 'absolute', left: 0, right: 0, height: 2,
                                    backgroundColor: '#0d7ff2',
                                    shadowColor: '#0d7ff2', shadowOpacity: 1, shadowRadius: 10, elevation: 5
                                }
                            ]}
                        />

                        {/* Floating Data Points */}
                        <Animated.View style={[animatedParticleStyle, { position: 'absolute', top: '30%', right: '15%', flexDirection: 'row', alignItems: 'center', gap: 4 }]}>
                            <View className="w-1.5 h-1.5 rounded-full bg-primary" />
                            <Text className="text-[10px] text-primary font-mono opacity-80">ENG-01</Text>
                        </Animated.View>
                        <Animated.View style={[animatedParticleStyle, { position: 'absolute', bottom: '25%', left: '15%', flexDirection: 'row', alignItems: 'center', gap: 4 }]}>
                            <View className="w-1.5 h-1.5 rounded-full bg-primary" />
                            <Text className="text-[10px] text-primary font-mono opacity-80">TRS-V2</Text>
                        </Animated.View>
                    </View>
                </View>

                {/* Headline Text */}
                <View className="w-full items-center mb-10">
                    <Text className="text-white text-[26px] font-bold leading-tight mb-2 text-center">
                        {failedDisplay ? (
                            <>진단 <Text className="text-red-400">실패</Text></>
                        ) : isComplete ? (
                            <>진단 <Text className="text-primary">완료</Text></>
                        ) : (
                            <>차량 정보를{'\n'}<Text className="text-primary">정밀 분석</Text> 중입니다...</>
                        )}
                    </Text>
                    <Text className="text-slate-400 text-sm font-normal leading-relaxed text-center px-4">
                        {failedDisplay
                            ? '오류가 발생했습니다. 확인을 누르면 진단 화면으로 이동합니다.'
                            : isComplete
                                ? `${completeTarget}(으)로 이동합니다.`
                                : 'AI가 차량의 상태를 실시간으로 진단하고\n잠재적인 위험 요소를 파악합니다.'}
                    </Text>
                </View>

                {/* Progress Section */}
                <View className="w-full gap-4 mb-5">
                    <View className="flex-row justify-between items-end px-1">
                        <View className="gap-1">
                            <Text className="text-primary text-xs font-bold tracking-widest uppercase">Status</Text>
                            <View className="flex-row items-center gap-2">
                                {failedDisplay ? (
                                    <MaterialIcons name="error-outline" size={14} color="#f87171" />
                                ) : isComplete ? (
                                    <MaterialIcons name="check-circle" size={14} color="#0d7ff2" />
                                ) : (
                                    <MaterialIcons name="sync" size={14} color="#9cabba" />
                                )}
                                <Text className="text-[#9cabba] text-sm font-medium">
                                    {failedDisplay
                                        ? '진단 실패'
                                        : isComplete
                                            ? '완료'
                                            : !effectiveSessionId
                                                ? '세션 정보를 찾을 수 없습니다.'
                                                : sseStatusMessage}
                                </Text>
                            </View>
                        </View>
                        <Text className="text-white text-3xl font-bold tracking-tighter">
                            {failedDisplay ? '—' : Math.round(sseProgress * 100)}%
                        </Text>
                    </View>

                    {/* Progress Bar Container */}
                    <View className="h-1.5 w-full bg-[#2a3848] rounded-full overflow-hidden relative">
                        {/* Fill */}
                        <View className="h-full bg-primary shadow-[0_0_10px_rgba(13,127,242,0.6)]" style={{ width: `${sseProgress * 100}%` }} />
                    </View>
                </View>

                {/* Technical Grid */}
                <View className="w-full flex-row flex-wrap gap-3">
                    <View className="w-full flex-row gap-3">
                        <StatusItem icon="memory" label="ECU System" status="Connecting..." />
                        <StatusItem icon="bolt" label="Battery" status="Voltage Stable" />
                    </View>
                    <View className="w-full flex-row gap-3">
                        <StatusItem icon="settings-suggest" label="Engine" status="Analyzing..." />
                        <StatusItem icon="water-drop" label="Fluids" status="Waiting" isWaiting />
                    </View>
                </View>

            </View>
            </SafeAreaView>
            {insets.bottom > 0 && (
                <View
                    style={{
                        position: 'absolute',
                        bottom: 0,
                        left: 0,
                        right: 0,
                        height: insets.bottom,
                        backgroundColor: '#101922',
                    }}
                />
            )}
        </View>
    );
}
