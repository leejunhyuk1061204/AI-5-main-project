import React, { useEffect, useRef, useState } from 'react';
import { View, Text, TouchableOpacity, Animated, Easing, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import { Audio } from 'expo-av';
import { Alert } from 'react-native';
import { diagnoseEngineSound } from '../api/aiApi';

export default function EngineSoundDiag() {
    const navigation = useNavigation<any>();
    const route = useRoute<any>();

    // State for Diagnosis Flow
    const [step, setStep] = useState(1); // 1: Record, 2: Analyze, 3: Result
    const [isRecording, setIsRecording] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false); // Validates start/stop actions

    // Recording Ref for thread safety
    const recordingRef = useRef<Audio.Recording | null>(null);

    // Legacy State (restored for UI compatibility if needed, though Ref is primary)
    const [recording, setRecording] = useState<Audio.Recording | null>(null);
    const [diagnosisResult, setDiagnosisResult] = useState<any>(null);

    // Animation values for each bar
    const animations = useRef([...Array(9)].map(() => new Animated.Value(1))).current;

    // Cleanup on Unmount
    useEffect(() => {
        return () => {
            if (recordingRef.current) {
                recordingRef.current.stopAndUnloadAsync();
            }
        };
    }, []);

    // Start Recording
    const startRecording = async () => {
        if (isProcessing) return;
        setIsProcessing(true);

        try {
            const permission = await Audio.requestPermissionsAsync();
            if (permission.status !== 'granted') {
                Alert.alert('권한 필요', '마이크 사용 권한이 필요합니다.');
                setIsProcessing(false);
                return;
            }

            await Audio.setAudioModeAsync({
                allowsRecordingIOS: true,
                playsInSilentModeIOS: true,
            });

            const { recording } = await Audio.Recording.createAsync(
                Audio.RecordingOptionsPresets.HIGH_QUALITY
            );
            recordingRef.current = recording; // Update Ref
            setIsRecording(true);
        } catch (err) {
            console.error('Failed to start recording', err);
            Alert.alert('오류', '녹음을 시작할 수 없습니다.');
        } finally {
            setIsProcessing(false);
        }
    };

    // Stop Recording & Analyze
    const stopRecording = async () => {
        if (!recordingRef.current || isProcessing) return;
        setIsProcessing(true);
        setIsRecording(false);
        setStep(2); // Move to Analysis Step

        try {
            const recording = recordingRef.current;
            const uri = recording.getURI(); // Get URI before unloading
            await recording.stopAndUnloadAsync();

            if (uri) {
                console.log('Recording stopped and stored at', uri);
                analyzeSound(uri);
            } else {
                throw new Error('No URI found');
            }
        } catch (error) {
            console.error(error);
            Alert.alert('오류', '녹음 파일을 저장하는 중 문제가 발생했습니다.');
            setStep(1);
        } finally {
            recordingRef.current = null;
            setIsProcessing(false);
        }
    };

    // Analyze Sound via API
    const analyzeSound = async (uri: string) => {
        try {
            const result = await diagnoseEngineSound(uri);
            setDiagnosisResult(result);

            if (route.params?.from === 'chatbot') {
                navigation.navigate('AiCompositeDiag', { diagnosisResult: result });
            } else {
                setStep(3); // Go to Result Screen
            }
        } catch (error) {
            Alert.alert('진단 실패', '서버 통신 중 오류가 발생했습니다.');
            setStep(1); // Reset to start
        }
    };

    const handleRecordToggle = () => {
        if (isProcessing) return;

        if (!isRecording && !recordingRef.current) {
            startRecording();
        } else {
            stopRecording();
        }
    };

    const barHeights = [32, 48, 64, 96, 56, 80, 40, 48, 24];

    return (
        <SafeAreaView className="flex-1 bg-[#101922]">
            <StatusBar style="light" />

            {/* Header */}
            <View className="flex-row items-center justify-between px-4 py-3">
                <TouchableOpacity
                    onPress={() => navigation.goBack()}
                    className="w-10 h-10 items-center justify-center rounded-full active:bg-white/10"
                >
                    <MaterialIcons name="arrow-back-ios" size={20} color="white" />
                </TouchableOpacity>
                <Text className="text-white text-lg font-bold">엔진 소리 진단</Text>
                <View className="w-10" />
            </View>

            {/* Progress Indicator */}
            {step < 3 && (
                <View className="px-6 pb-2">
                    <View className="flex-row items-center justify-between mb-2">
                        <Text className="text-xs font-medium text-slate-400">{step}단계</Text>
                        <Text className="text-xs font-medium text-[#0d7ff2]">3단계 중 {step}</Text>
                    </View>
                    <View className="flex-row gap-2 h-1.5 w-full">
                        <View className={`flex-1 rounded-full ${step >= 1 ? 'bg-[#0d7ff2]' : 'bg-[#1a2430]'}`} />
                        <View className={`flex-1 rounded-full ${step >= 2 ? 'bg-[#0d7ff2]' : 'bg-[#1a2430]'}`} />
                        <View className={`flex-1 rounded-full ${step >= 3 ? 'bg-[#0d7ff2]' : 'bg-[#1a2430]'}`} />
                    </View>
                </View>
            )}

            {/* Main Content Area */}
            <View className="flex-1 items-center justify-center px-6 relative">

                {/* Step 1 & 2: Visualization UI */}
                {step <= 2 && (
                    <>
                        {/* Context Text */}
                        <View className="items-center mb-12 z-10">
                            <Text className="text-2xl font-bold text-white text-center leading-9 mb-3">
                                {step === 1
                                    ? (isRecording ? "소리를 녹음 중입니다..." : "엔진 시동을 걸고\n소리를 녹음해 주세요")
                                    : "AI가 소리를 분석 중입니다..."}
                            </Text>
                            <Text className="text-sm text-slate-400 text-center leading-5">
                                {step === 1
                                    ? "정확한 분석을 위해 주변 소음을\n최소화해 주시기 바랍니다."
                                    : "잠시만 기다려주세요\n엔진과 부품의 상태를 정밀 진단하고 있습니다."}
                            </Text>
                        </View>

                        {/* Waveform Visualization */}
                        <View className="relative items-center justify-center w-full h-40 mb-12">
                            {/* Background Glow */}
                            <View className={`absolute inset-0 rounded-full blur-3xl opacity-50 ${step === 2 ? 'bg-purple-500/20' : 'bg-[#0d7ff2]/10'}`} />

                            {/* Visual Bars */}
                            <View className="flex-row items-center justify-center gap-1.5 h-full z-10">
                                {animations.map((anim, index) => (
                                    <Animated.View
                                        key={index}
                                        style={{
                                            width: 6,
                                            height: barHeights[index],
                                            backgroundColor: step === 2 ? '#a855f7' : '#0d7ff2', // Purple for analysis
                                            borderRadius: 9999,
                                            transform: [{ scaleY: anim }],
                                            shadowColor: step === 2 ? '#a855f7' : '#0d7ff2',
                                            shadowOffset: { width: 0, height: 0 },
                                            shadowOpacity: 0.6,
                                            shadowRadius: 15,
                                            opacity: 0.8
                                        }}
                                    />
                                ))}
                            </View>
                        </View>

                        {/* Step 1 Extra: Distance Guide */}
                        {step === 1 && (
                            <View className="w-full max-w-sm bg-[#1a2430] rounded-xl p-4 flex-row items-center gap-4 border border-slate-800">
                                <View className="w-12 h-12 rounded-lg bg-[#0d7ff2]/10 items-center justify-center">
                                    <MaterialIcons name="straighten" size={24} color="#0d7ff2" />
                                </View>
                                <View className="flex-1">
                                    <Text className="text-sm font-semibold text-white">거리 유지</Text>
                                    <Text className="text-xs text-slate-400 mt-0.5">보닛에서 약 30cm 거리를 유지해 주세요</Text>
                                </View>
                            </View>
                        )}
                    </>
                )}

                {/* Step 3: Result UI */}
                {step === 3 && (
                    <View className="w-full items-center">
                        <View className="w-32 h-32 rounded-full border-4 border-[#0d7ff2] items-center justify-center mb-6 shadow-[0_0_30px_rgba(13,127,242,0.3)] bg-[#0d7ff2]/10">
                            <MaterialIcons name="check-circle" size={64} color="#0d7ff2" />
                        </View>

                        <Text className="text-3xl font-bold text-white mb-2">
                            진단 결과: {diagnosisResult?.result === 'NORMAL' ? '정상' : '이상 감지'}
                        </Text>
                        <View className="bg-[#1a2430] px-4 py-1.5 rounded-full border border-slate-700 mb-8">
                            <Text className="text-sm text-slate-300">종합 점수 <Text className="text-[#0d7ff2] font-bold">98점</Text></Text>
                        </View>

                        <View className="w-full bg-[#1a2430] rounded-2xl p-6 border border-slate-800 mb-8">
                            <Text className="text-lg font-bold text-white mb-3">상세 분석</Text>
                            <View className="gap-3">
                                <Text className="text-slate-300 leading-5">
                                    {diagnosisResult?.description || '분석 결과가 없습니다.'}
                                </Text>
                            </View>
                        </View>

                        <TouchableOpacity
                            onPress={() => navigation.goBack()}
                            className="w-full bg-[#1b2127] border border-white/10 py-4 rounded-xl items-center active:bg-white/5"
                        >
                            <Text className="text-white font-bold text-base">메인으로 돌아가기</Text>
                        </TouchableOpacity>
                    </View>
                )}

            </View>

            {/* Footer / Action Area (Only for Step 1) */}
            {step === 1 && (
                <View className="p-6 items-center gap-4 bg-[#101922] pb-10">
                    {/* Record/Stop Button */}
                    <TouchableOpacity
                        onPress={handleRecordToggle}
                        className={`relative items-center justify-center w-20 h-20 rounded-full shadow-lg active:scale-95 transition-all ${isRecording ? 'bg-red-500 shadow-red-500/40' : 'bg-[#0d7ff2] shadow-blue-500/40'}`}
                    >
                        {isRecording && (
                            <View className="absolute inset-0 rounded-full border-2 border-white/30 animate-ping" />
                        )}
                        <MaterialIcons
                            name={isRecording ? "stop" : "mic"}
                            size={32}
                            color="white"
                        />
                    </TouchableOpacity>

                    <Text className={`text-sm font-medium ${isRecording ? 'text-red-400 animate-pulse' : 'text-slate-500'}`}>
                        {isRecording ? "녹음 중..." : "녹음 준비 완료"}
                    </Text>

                    {/* Safety Note */}
                    <View className="flex-row items-center gap-1.5 mt-2 opacity-60">
                        <MaterialIcons name="warning" size={16} color="#f59e0b" />
                        <Text className="text-[10px] text-slate-400">안전을 위해 주차 브레이크를 꼭 확인하세요</Text>
                    </View>
                </View>
            )}
        </SafeAreaView>
    );
}
