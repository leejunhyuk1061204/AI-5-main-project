import React, { useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { View, Text, TouchableOpacity, ImageBackground, Dimensions, Platform, Alert } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { CommonActions, useRoute, RouteProp } from '@react-navigation/native';
import { StatusBar } from 'expo-status-bar';
import { LinearGradient } from 'expo-linear-gradient';
import Animated, {
    useSharedValue,
    useAnimatedStyle,
    withRepeat,
    withTiming,
    withSequence,
    Easing
} from 'react-native-reanimated';

import EventSource from "react-native-sse";
import { BASE_URL } from '../api/axios';
import { getDiagnosisSessionStatus } from '../api/aiApi';
import { useAiDiagnosisStore } from '../store/useAiDiagnosisStore';

const { width } = Dimensions.get('window');

// Route 파라미터 타입 정의
type ActiveLoadingParams = {
    vehicleId?: string;
};

export default function ObdDiagLoading({ navigation }: any) {
    const insets = useSafeAreaInsets();
    const route = useRoute<RouteProp<{ ObdDiagLoading: ActiveLoadingParams }, 'ObdDiagLoading'>>();
    const vehicleId = route.params?.vehicleId;
    const { currentSessionId } = useAiDiagnosisStore();

    // SSE State
    const [progress, setProgress] = React.useState(0.0);
    const [statusMessage, setStatusMessage] = React.useState("서버 연결 대기 중...");
    const [token, setToken] = React.useState<string | null>(null);

    // Animations
    const scanLineY = useSharedValue(0);
    const particleOpacity = useSharedValue(0.3);
    const rotate = useSharedValue(0);

    // 1. Get Token
    useEffect(() => {
        AsyncStorage.getItem('accessToken').then(t => {
            if (t) {
                setToken(t);
            } else {
                console.error("[ObdDiagLoading] No Access Token found!");
                setStatusMessage("인증 정보를 찾을 수 없습니다.");
            }
        });
    }, []);

    // 2. Connect SSE
    useEffect(() => {
        if (!currentSessionId) {
            console.error("[ObdDiagLoading] No Session ID found!");
            setStatusMessage("세션 정보를 찾을 수 없습니다.");
            return;
        }

        if (!token) {
            // Wait for token
            return;
        }

        const url = `${BASE_URL}/api/v1/ai/diagnose/session/${currentSessionId}/sse`;
        console.log(`[ObdDiagLoading] Connecting SSE: ${url}`);

        // IMPORTANT: Pass Authorization Header for secured endpoint
        const es = new EventSource(url, {
            headers: {
                Authorization: `Bearer ${token}`
            }
        });

        const handleOpen = () => {
            console.log("[SSE] Connected!");
            setStatusMessage("서버 연결 성공 (진단 시작)");
            setProgress(0.1);
        };

        const handleStep1 = (event: any) => {
            console.log("[SSE] Step 1:", event.data);
            setStatusMessage("진단 요청 접수 완료");
            setProgress(0.2);
        };
        const handleStep2 = (event: any) => {
            console.log("[SSE] Step 2:", event.data);
            setStatusMessage("멀티미디어 데이터 전처리 완료");
            setProgress(0.4);
        };
        const handleStep3 = (event: any) => {
            console.log("[SSE] Step 3:", event.data);
            setStatusMessage("AI 정밀 분석 완료 (시각/청각/OBD)");
            setProgress(0.6);
        };
        const handleStep4 = (event: any) => {
            console.log("[SSE] Step 4:", event.data);
            setStatusMessage("결함 원인 추론 및 지식 검색 완료");
            setProgress(0.8);
        };
        const handleFailed = (event: any) => {
            console.log("[SSE] Failed:", event.data);
            const message = event?.data || "AI 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.";
            setStatusMessage(message);
            setProgress(1.0);

            Alert.alert(
                "진단 실패",
                message,
                [
                    {
                        text: "확인",
                        onPress: () => {
                            // 이전 화면(진단 시작 화면 등)으로 복귀
                            navigation.goBack();
                        }
                    }
                ]
            );
        };
        const handleStep5 = async (event: any) => {
            console.log("[SSE] Step 5:", event.data);
            setStatusMessage("최종 진단 완료 (결과 확인 중)");
            setProgress(1.0);

            if (!currentSessionId) {
                setTimeout(() => navigation.replace('ObdDiagResult'), 1000);
                return;
            }
            try {
                const data = await getDiagnosisSessionStatus(currentSessionId);
                const status = (data?.status || '').toUpperCase();
                const responseMode = data?.responseMode || data?.response_mode || '';

                const isInteractive = status === 'ACTION_REQUIRED' || status === 'INTERACTIVE' || responseMode === 'INTERACTIVE';

                setTimeout(() => {
                    if (isInteractive) {
                        navigation.replace('AiDiagChat', { sessionId: currentSessionId, vehicleId: vehicleId ?? undefined });
                    } else {
                        navigation.replace('ObdDiagResult');
                    }
                }, 800);
            } catch (e) {
                console.warn("[ObdDiagLoading] Step5 status fetch failed, going to result:", e);
                setTimeout(() => navigation.replace('ObdDiagResult'), 1000);
            }
        };

        const handleError = (error: any) => {
            // console.error("[SSE] Error:", error);
            // Ignore simple connection errors/retries for now, or handle specifically
        };

        // Cast custom event names to any to avoid TS errors
        es.addEventListener("open" as any, handleOpen);
        es.addEventListener("step1" as any, handleStep1);
        es.addEventListener("step2" as any, handleStep2);
        es.addEventListener("step3" as any, handleStep3);
        es.addEventListener("step4" as any, handleStep4);
        es.addEventListener("step5" as any, handleStep5);
        es.addEventListener("failed" as any, handleFailed);
        es.addEventListener("error" as any, handleError);

        // Animations start
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

        return () => {
            es.close();
            // Optional: reset animations if needed
        };
    }, [currentSessionId, token]);

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
            <StatusBar style="light" />

            {/* Header */}
            <View
                className="z-10 bg-transparent absolute top-0 w-full"
                style={{ paddingTop: insets.top }}
            >
                <View className="flex-row items-center justify-between px-4 py-3">
                    <Text className="text-white text-lg font-bold tracking-tight uppercase opacity-90 pr-10 flex-1 text-center">
                        AI Diagnostics
                    </Text>
                </View>
            </View>

            {/* Main Content */}
            <View className="flex-1 items-center justify-center px-6 pb-8">

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
                        차량 데이터를{'\n'}
                        <Text className="text-primary">정밀 분석</Text> 중입니다...
                    </Text>
                    <Text className="text-slate-400 text-sm font-normal leading-relaxed text-center px-4">
                        AI가 차량의 상태를 실시간으로 진단하고{'\n'}잠재적인 위험 요소를 파악합니다.
                    </Text>
                </View>

                {/* Progress Section */}
                <View className="w-full gap-4 mb-5">
                    <View className="flex-row justify-between items-end px-1">
                        <View className="gap-1">
                            <Text className="text-primary text-xs font-bold tracking-widest uppercase">Status</Text>
                            <View className="flex-row items-center gap-2">
                                {/* Simple spin animation replacement just with icon for now or reusable spin */}
                                <MaterialIcons name="sync" size={14} color="#9cabba" className="animate-spin" />
                                {/** No duplicate icon needed, removed duplicate from previous bad view */}
                                <Text className="text-[#9cabba] text-sm font-medium">{statusMessage}</Text>
                            </View>
                        </View>
                        <Text className="text-white text-3xl font-bold tracking-tighter">{Math.round(progress * 100)}%</Text>
                    </View>

                    {/* Progress Bar Container */}
                    <View className="h-1.5 w-full bg-[#2a3848] rounded-full overflow-hidden relative">
                        {/* Fill */}
                        <View className="h-full bg-primary shadow-[0_0_10px_rgba(13,127,242,0.6)]" style={{ width: `${progress * 100}%` }} />
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
        </View>
    );
}
