import React, { useEffect, useRef, useState } from 'react';
import { View, Text, TouchableOpacity, Animated, ActivityIndicator } from 'react-native';
import { useAlertStore } from '../store/useAlertStore';
import { useAiDiagnosisStore } from '../store/useAiDiagnosisStore';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import { Audio } from 'expo-av';
import * as DocumentPicker from 'expo-document-picker';
import { diagnoseEngineSound, replyToDiagnosisSession } from '../api/aiApi';
import BaseScreen from '../components/layout/BaseScreen';

const RecordingText = () => {
    const opacity = React.useRef(new Animated.Value(1)).current;

    useEffect(() => {
        const animation = Animated.loop(
            Animated.sequence([
                Animated.timing(opacity, {
                    toValue: 0.3,
                    duration: 800,
                    useNativeDriver: true,
                }),
                Animated.timing(opacity, {
                    toValue: 1,
                    duration: 800,
                    useNativeDriver: true,
                }),
            ])
        );
        animation.start();
        return () => animation.stop();
    }, []);

    return (
        <Animated.Text
            style={{ opacity }}
            className="text-sm font-medium text-white"
        >
            녹음 중...
        </Animated.Text>
    );
};

export default function EngineSoundDiag() {
    const navigation = useNavigation<any>();
    const route = useRoute<any>();

    // State for Diagnosis Flow
    const [step, setStep] = useState(1); // 1: Record/Review, 2: Analyze, 3: Result
    const [isRecording, setIsRecording] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [recordedUri, setRecordedUri] = useState<string | null>(null);
    const [sound, setSound] = useState<Audio.Sound | null>(null);
    const [isPlaying, setIsPlaying] = useState(false);

    // Recording Ref for thread safety
    const recordingRef = useRef<Audio.Recording | null>(null);
    const [diagnosisResult, setDiagnosisResult] = useState<any>(null);

    // Animation values for each bar
    const animations = useRef([...Array(9)].map(() => new Animated.Value(1))).current;

    // Cleanup on Unmount
    useEffect(() => {
        return () => {
            if (recordingRef.current) {
                recordingRef.current.stopAndUnloadAsync();
            }
            if (sound) {
                sound.unloadAsync();
            }
        };
    }, [sound]);

    // Animation Effect for Analysis or Recording
    useEffect(() => {
        if (step === 2 || isRecording) {
            const loops = animations.map((anim, i) => {
                return Animated.loop(
                    Animated.sequence([
                        Animated.timing(anim, {
                            toValue: Math.random() * 0.5 + 0.5, // Random scale between 0.5 and 1.0
                            duration: 200 + Math.random() * 300,
                            useNativeDriver: true,
                        }),
                        Animated.timing(anim, {
                            toValue: 1.2, // Scale up to 1.2
                            duration: 200 + Math.random() * 300,
                            useNativeDriver: true,
                        }),
                        Animated.timing(anim, {
                            toValue: 1,
                            duration: 200,
                            useNativeDriver: true,
                        })
                    ])
                );
            });

            loops.forEach(loop => loop.start());

            return () => {
                loops.forEach(loop => loop.stop());
                // Reset values
                animations.forEach(anim => {
                    anim.setValue(1);
                });
            };
        }
    }, [step, isRecording]);

    // Start Recording
    const startRecording = async () => {
        if (isProcessing) return;
        setIsProcessing(true);
        setRecordedUri(null); // Clear previous recording

        try {
            const permission = await Audio.requestPermissionsAsync();
            if (permission.status !== 'granted') {
                useAlertStore.getState().showAlert('권한 필요', '마이크 사용 권한이 필요합니다.', 'WARNING');
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
            recordingRef.current = recording;
            setIsRecording(true);
        } catch (err) {
            console.error('Failed to start recording', err);
            useAlertStore.getState().showAlert('오류', '녹음을 시작할 수 없습니다.', 'ERROR');
        } finally {
            setIsProcessing(false);
        }
    };

    // Stop Recording
    const stopRecording = async () => {
        if (!recordingRef.current || isProcessing) return;
        setIsProcessing(true);
        setIsRecording(false);
        // Do NOT set step 2 here, stay in step 1 to review

        try {
            const recording = recordingRef.current;
            await recording.stopAndUnloadAsync();
            const uri = recording.getURI();

            if (uri) {
                setRecordedUri(uri);
            } else {
                throw new Error('No URI found');
            }
        } catch (error) {
            console.error(error);
            useAlertStore.getState().showAlert('오류', '녹음 파일을 저장하는 중 문제가 발생했습니다.', 'ERROR');
        } finally {
            recordingRef.current = null;
            setIsProcessing(false);
        }
    };

    // Play Recording
    const playRecording = async () => {
        if (!recordedUri) return;

        try {
            if (sound) {
                await sound.unloadAsync();
            }

            const { sound: newSound } = await Audio.Sound.createAsync(
                { uri: recordedUri },
                { shouldPlay: true }
            );
            setSound(newSound);
            setIsPlaying(true);

            newSound.setOnPlaybackStatusUpdate((status) => {
                if (status.isLoaded) {
                    if (status.didJustFinish) {
                        setIsPlaying(false);
                    }
                }
            });
        } catch (error) {
            console.error('Failed to play sound', error);
            useAlertStore.getState().showAlert('오류', '녹음 파일을 재생할 수 없습니다.', 'ERROR');
        }
    };

    // Stop Playback
    const stopPlayback = async () => {
        if (sound) {
            await sound.stopAsync();
            setIsPlaying(false);
        }
    };

    // Pick Audio File
    const pickAudioFile = async () => {
        if (isProcessing) return;
        try {
            const result = await DocumentPicker.getDocumentAsync({
                type: 'audio/*',
                copyToCacheDirectory: true,
            });

            if (!result.canceled && result.assets && result.assets.length > 0) {
                const uri = result.assets[0].uri;
                setRecordedUri(uri);
                // Stay in step 1 to review
            }
        } catch (err) {
            console.error('Failed to pick document', err);
            useAlertStore.getState().showAlert('오류', '파일을 선택하는 중 문제가 발생했습니다.', 'ERROR');
        }
    };

    // Confirm & Analyze
    const handleConfirmAnalysis = () => {
        if (recordedUri) {
            setStep(2);
            analyzeSound(recordedUri);
        }
    };

    // Analyze Sound via API
    const analyzeSound = async (uri: string) => {
        const sessionId = route.params?.sessionId;
        const vehicleId = route.params?.vehicleId || useAiDiagnosisStore.getState().selectedVehicleId;

        if (!vehicleId) {
            useAlertStore.getState().showAlert('차량 미선택', '분석을 진행할 차량 정보를 찾을 수 없습니다. 차량을 먼저 선택해 주세요.', 'WARNING');
            return;
        }

        executeSoundAnalysis(uri, sessionId || null);
    };

    const executeSoundAnalysis = async (uri: string, sessionId: string | null) => {
        const { updateStatus, setVehicleId } = useAiDiagnosisStore.getState();
        const vehicleId = route.params?.vehicleId || useAiDiagnosisStore.getState().selectedVehicleId;
        if (!vehicleId) return;
        try {
            let result;
            if (sessionId) {
                // INTERACTIVE 모드 답변인 경우
                result = await replyToDiagnosisSession(sessionId as string, {
                    userResponse: "엔진 소리를 녹음했습니다.",
                    vehicleId: vehicleId as string
                }, undefined, uri);

                useAiDiagnosisStore.setState({ isWaitingForAi: true });
            } else {
                // 신규 진단인 경우
                useAiDiagnosisStore.setState({
                    status: 'PROCESSING',
                    loadingMessage: '엔진 소리를 분석하고 있습니다...',
                    messages: [],
                    diagResult: null,
                    currentSessionId: null
                });

                result = await diagnoseEngineSound(uri, vehicleId as string);
            }

            setDiagnosisResult(result);

            if (result.sessionId) {
                setVehicleId(vehicleId as string);
                useAiDiagnosisStore.setState({ currentSessionId: result.sessionId });
                await updateStatus(result.sessionId);
            } else {
                setStep(3);
            }
        } catch (error: any) {
            console.error(error);
            useAlertStore.getState().showAlert('진단 실패', error.message || '서버 통신 중 오류가 발생했습니다.', 'ERROR');
            setStep(1);
            useAiDiagnosisStore.setState({ status: 'IDLE' });
        }
    };

    // Polling Effect (소리 진단 화면용)
    const { status, currentSessionId, updateStatus } = useAiDiagnosisStore();

    useEffect(() => {
        let intervalId: NodeJS.Timeout;
        if (status === 'PROCESSING' && currentSessionId) {
            intervalId = setInterval(() => {
                updateStatus(currentSessionId);
            }, 2000);
        }
        return () => {
            if (intervalId) clearInterval(intervalId);
        };
    }, [status, currentSessionId]);

    // Status Watcher: 상태 변화에 따른 네비게이션
    // Status Watcher: 상태 변화에 따른 네비게이션
    const isInitialMount = useRef(true);

    useEffect(() => {
        if (!currentSessionId) return;

        // Skip the first check if status is already INTERACTIVE/ACTION_REQUIRED
        if (isInitialMount.current) {
            isInitialMount.current = false;
            if (status === 'INTERACTIVE' || status === 'ACTION_REQUIRED') {
                return;
            }
        }

        if (status === 'INTERACTIVE' || status === 'ACTION_REQUIRED') {
            navigation.navigate('AiDiagChat', {
                sessionId: currentSessionId,
                vehicleId: route.params?.vehicleId
            });
        } else if (status === 'REPORT') {
            navigation.replace('DiagnosisReport', {
                reportData: { sessionId: currentSessionId }
            });
        }
    }, [status, currentSessionId]);

    const handleRecordToggle = () => {
        if (isProcessing) return;

        if (isPlaying) {
            stopPlayback();
            return;
        }

        if (isRecording) {
            stopRecording();
        } else {
            // If we have a recording, this button might act as "Re-record" if we want, 
            // but let's handle that in the render logic to keep it clean.
            // For now, if not recording and no uri, start.
            startRecording();
        }
    };

    // Retake handler
    const handleRetake = () => {
        setRecordedUri(null);
        if (isPlaying) stopPlayback();
    }

    const barHeights = [32, 48, 64, 96, 56, 80, 40, 48, 24];

    const HeaderCustom = (
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
    );

    return (
        <BaseScreen
            header={HeaderCustom}
            scrollable={step === 3} // Only result screen might need scrolling
            padding={false}
        >
            <View className="flex-1 items-center justify-center relative">
                {/* Progress Indicator */}
                {step < 3 && (
                    <View className="w-full pb-8">
                        <View className="flex-row items-center justify-between mb-2 px-2">
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

                {/* Step 1 & 2: Visualization UI */}
                {step <= 2 && (
                    <>
                        <View className="items-center mb-12">
                            <Text className="text-2xl font-bold text-white text-center leading-9 mb-3">
                                {step === 1
                                    ? (recordedUri
                                        ? "녹음된 소리를 확인해 주세요"
                                        : (isRecording ? "소리를 녹음 중입니다..." : "엔진 시동을 걸고\n소리를 녹음해 주세요"))
                                    : "AI가 소리를 분석 중입니다..."}
                            </Text>
                            <Text className="text-sm text-slate-400 text-center leading-5">
                                {step === 1
                                    ? (recordedUri ? "재생 버튼을 눌러 소리를 확인할 수 있습니다.\n문제가 없다면 진단 시작 버튼을 눌러주세요." : "정확한 분석을 위해 주변 소음을\n최소화해 주시기 바랍니다.")
                                    : "잠시만 기다려주세요\n엔진과 부품의 상태를 정밀 진단하고 있습니다."}
                            </Text>
                        </View>

                        <View className="relative items-center justify-center w-full h-40 mb-12">
                            <View className="flex-row items-center justify-center gap-1.5 h-full z-10">
                                {animations.map((anim, index) => (
                                    <Animated.View
                                        key={index}
                                        style={{
                                            width: 6,
                                            height: barHeights[index],
                                            backgroundColor: (step === 2 || isPlaying || isRecording) ? '#a855f7' : '#0d7ff2',
                                            borderRadius: 9999,
                                            transform: [{ scaleY: anim }],
                                            shadowColor: (step === 2 || isPlaying || isRecording) ? '#a855f7' : '#0d7ff2',
                                            shadowOffset: { width: 0, height: 0 },
                                            shadowOpacity: 0.6,
                                            shadowRadius: 15,
                                            opacity: 0.8
                                        }}
                                    />
                                ))}
                            </View>
                        </View>

                        {step === 1 && (
                            <View className="w-full flex-col items-center gap-8">
                                {/* Recording/Playback Controls */}
                                {!recordedUri ? (
                                    /* Recording State */
                                    <View className="items-center gap-8 w-full flex-row justify-center mt-4">
                                        <View className="items-center gap-4">
                                            <TouchableOpacity
                                                onPress={handleRecordToggle}
                                                className={`relative items-center justify-center w-20 h-20 rounded-full shadow-lg active:scale-95 transition-all ${isRecording ? 'bg-red-500 shadow-red-500/40' : 'bg-[#0d7ff2] shadow-blue-500/40'}`}
                                            >
                                                <MaterialIcons
                                                    name={isRecording ? "stop" : "mic"}
                                                    size={32}
                                                    color="white"
                                                />
                                            </TouchableOpacity>
                                            {isRecording ? (
                                                <RecordingText />
                                            ) : (
                                                <Text className="text-sm font-medium text-slate-500">
                                                    녹음 시작
                                                </Text>
                                            )}
                                        </View>

                                        {!isRecording && (
                                            <View className="items-center gap-4">
                                                <TouchableOpacity
                                                    onPress={pickAudioFile}
                                                    disabled={isProcessing}
                                                    className="relative items-center justify-center w-20 h-20 rounded-full bg-[#1a2430] border border-slate-700 shadow-lg active:scale-95 transition-all"
                                                >
                                                    <MaterialIcons
                                                        name="file-present"
                                                        size={32}
                                                        color="white"
                                                    />
                                                </TouchableOpacity>
                                                <Text className="text-sm font-medium text-slate-500">파일 선택</Text>
                                            </View>
                                        )}
                                    </View>
                                ) : (
                                    /* Review State */
                                    <View className="w-full items-center">
                                        {/* Play/Pause Button - Centered */}
                                        <TouchableOpacity
                                            onPress={isPlaying ? stopPlayback : playRecording}
                                            className="w-24 h-24 rounded-full bg-[#0d7ff2] items-center justify-center shadow-lg shadow-blue-500/30 mb-10"
                                        >
                                            <MaterialIcons name={isPlaying ? "pause" : "play-arrow"} size={48} color="white" style={{ marginLeft: isPlaying ? 0 : 4 }} />
                                        </TouchableOpacity>

                                        {/* Action Buttons Row */}
                                        <View className="w-full px-4 mb-4">
                                            <View className="flex-row items-center gap-3 w-full">
                                                {/* Retake */}
                                                <TouchableOpacity
                                                    onPress={handleRetake}
                                                    className="flex-1 h-14 bg-[#1e293b] rounded-xl items-center justify-center border border-slate-600 active:bg-slate-700"
                                                >
                                                    <Text className="text-slate-300 font-bold text-base">재녹음</Text>
                                                </TouchableOpacity>

                                                {/* Analyze */}
                                                <TouchableOpacity
                                                    onPress={handleConfirmAnalysis}
                                                    className="flex-1 h-14 bg-[#0d7ff2] rounded-xl items-center justify-center border border-[#0d7ff2] active:bg-blue-600"
                                                >
                                                    <Text className="text-white font-bold text-base">진단 시작</Text>
                                                </TouchableOpacity>
                                            </View>
                                        </View>
                                    </View>
                                )}
                            </View>
                        )}
                    </>
                )}

                {/* Step 3: Result UI */}
                {step === 3 && (
                    <View className="w-full items-center py-4">
                        <View className="w-32 h-32 rounded-full border-4 border-[#0d7ff2] items-center justify-center mb-6 shadow-[0_0_30px_rgba(13,127,242,0.3)] bg-[#0d7ff2]/10">
                            <ActivityIndicator size="small" color="#0d7ff2" />
                        </View>

                        <Text className="text-3xl font-bold text-white mb-2">
                            진단 결과: {diagnosisResult?.result === 'NORMAL' ? '정상' : '이상 감지'}
                        </Text>
                        <View className="bg-[#1a2430] px-4 py-1.5 rounded-full border border-slate-700 mb-8">
                            <Text className="text-sm text-slate-300">종합 점수 <Text className="text-[#0d7ff2] font-bold">98점</Text></Text>
                        </View>

                        <View className="w-full bg-[#1a2430] rounded-2xl p-6 border border-slate-800 mb-8">
                            <Text className="text-lg font-bold text-white mb-3">상세 분석</Text>
                            <Text className="text-slate-300 leading-5">
                                {diagnosisResult?.description || '분석 결과가 없습니다.'}
                            </Text>
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
        </BaseScreen>
    );
}
