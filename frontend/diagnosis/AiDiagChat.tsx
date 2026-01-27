import React, { useState, useEffect, useRef } from 'react';
import { View, Text, TouchableOpacity, TextInput, ActivityIndicator, ScrollView, Animated } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
// import { useNavigation, useRoute } from '@react-navigation/native'; // Removed
import Header from '../header/Header';
import BaseScreen from '../components/layout/BaseScreen';
import { useAiDiagnosisStore } from '../store/useAiDiagnosisStore';
import { useUIStore } from '../store/useUIStore';
import { useVehicleStore } from '../store/useVehicleStore';

const DotPulse = () => {
    const dot1 = useRef(new Animated.Value(0.3)).current;
    const dot2 = useRef(new Animated.Value(0.3)).current;
    const dot3 = useRef(new Animated.Value(0.3)).current;

    useEffect(() => {
        const createAnim = (val: Animated.Value, delay: number) => {
            return Animated.loop(
                Animated.sequence([
                    Animated.delay(delay),
                    Animated.timing(val, { toValue: 1, duration: 400, useNativeDriver: true }),
                    Animated.timing(val, { toValue: 0.3, duration: 400, useNativeDriver: true }),
                ])
            );
        };
        Animated.parallel([
            createAnim(dot1, 0),
            createAnim(dot2, 200),
            createAnim(dot3, 400),
        ]).start();
    }, []);

    return (
        <View className="flex-row ml-1">
            <Animated.Text style={{ opacity: dot1, color: '#9cabba' }} className="text-[15px] font-bold">.</Animated.Text>
            <Animated.Text style={{ opacity: dot2, color: '#9cabba' }} className="text-[15px] font-bold">.</Animated.Text>
            <Animated.Text style={{ opacity: dot3, color: '#9cabba' }} className="text-[15px] font-bold">.</Animated.Text>
        </View>
    );
};

// props로 직접 받기
export default function AiDiagChat({ navigation, route }: any) {
    const scrollRef = useRef<ScrollView>(null);
    const [userInput, setUserInput] = useState('');
    const { primaryVehicle } = useVehicleStore();

    const {
        status,
        messages,
        diagResult,
        sendReply,
        updateStatus,
        currentSessionId,
        isWaitingForAi,
        requestedAction,
        startDiagnosis,
        reset,
        loadingMessage
    } = useAiDiagnosisStore();

    // Auto-Report Navigation
    useEffect(() => {
        if (status === 'REPORT') {
            console.log("[AiDiagChat] Diagnosis COMPLETED. Navigating to Report Screen.");
            navigation.replace('DiagnosisReport', {
                sessionId: currentSessionId,
                reportData: diagResult
            });
        }
    }, [status, currentSessionId, diagResult, navigation]);

    // Initial checks
    useEffect(() => {
        if (!currentSessionId && route.params?.autoStart && route.params?.vehicleId) {
            startDiagnosis(route.params.vehicleId);
        }
    }, [route.params?.autoStart, route.params?.vehicleId]);


    // Auto-scroll
    const scrollToEnd = (animated = false) => {
        scrollRef.current?.scrollToEnd({ animated });
    };

    useEffect(() => {
        const timer = setTimeout(() => {
            scrollRef.current?.scrollToEnd({ animated: true });
        }, 100);
        return () => clearTimeout(timer);
    }, [messages, isWaitingForAi]);

    // Polling Effect
    useEffect(() => {
        let intervalId: NodeJS.Timeout;
        const shouldPoll = (status === 'PROCESSING' || status === 'REPLY_PROCESSING' || isWaitingForAi) && currentSessionId;

        if (shouldPoll) {
            intervalId = setInterval(() => {
                updateStatus(currentSessionId);
            }, 2000);
        }
        return () => {
            if (intervalId) clearInterval(intervalId);
        };
    }, [status, currentSessionId, isWaitingForAi]);

    // Debug logging
    console.log('[AiDiagChat] Rendered via Props. Navigation available:', !!navigation);

    const handleSend = async () => {
        if (!userInput.trim()) return;
        const msg = userInput;
        setUserInput('');
        await sendReply(msg);
    };

    const [isMenuOpen, setIsMenuOpen] = useState(false);

    const handleCamera = () => {
        setIsMenuOpen(false);
        navigation.navigate('Filming', { sessionId: currentSessionId, vehicleId: route.params?.vehicleId });
    };

    const handleMic = () => {
        setIsMenuOpen(false);
        navigation.navigate('EngineSoundDiag', { sessionId: currentSessionId, vehicleId: route.params?.vehicleId });
    };

    const handleGallery = () => {
        setIsMenuOpen(false);
        navigation.navigate('Filming', { sessionId: currentSessionId, vehicleId: route.params?.vehicleId });
    };

    const toggleMenu = () => setIsMenuOpen(!isMenuOpen);

    return (
        <BaseScreen
            header={<Header navigation={navigation} />}
            footer={
                <View
                    className="px-6 py-4 bg-background-dark border-t border-white/5"
                    style={{ minHeight: 80 }}
                >
                    {/* Dynamic Action Buttons (Requested Actions) */}
                    {requestedAction && !isWaitingForAi && (
                        <View className="flex-row justify-center gap-3 mb-4 px-6">
                            {requestedAction === 'CAPTURE_PHOTO' && (
                                <TouchableOpacity
                                    onPress={handleCamera}
                                    className="bg-primary/20 border border-primary px-4 py-2.5 rounded-full flex-row items-center gap-2"
                                >
                                    <MaterialIcons name="photo-camera" size={18} color="#0d7ff2" />
                                    <Text className="text-primary font-bold text-sm">사진 촬영하기</Text>
                                </TouchableOpacity>
                            )}
                            {requestedAction === 'RECORD_AUDIO' && (
                                <TouchableOpacity
                                    onPress={handleMic}
                                    className="bg-secondary/20 border border-secondary px-4 py-2.5 rounded-full flex-row items-center gap-2"
                                >
                                    <MaterialIcons name="mic" size={18} color="#a855f7" />
                                    <Text className="text-secondary font-bold text-sm">소리 녹음하기</Text>
                                </TouchableOpacity>
                            )}
                        </View>
                    )}

                    {/* Media Attachment Menu (Proactive) */}
                    {isMenuOpen && (
                        <View className="flex-row justify-around mb-4 bg-surface-card p-4 rounded-xl border border-white/10 mx-1">
                            <TouchableOpacity onPress={handleCamera} className="items-center gap-2">
                                <View className="w-12 h-12 rounded-full bg-blue-500/20 items-center justify-center border border-blue-500/30">
                                    <MaterialIcons name="camera-alt" size={24} color="#3b82f6" />
                                </View>
                                <Text className="text-slate-300 text-xs font-medium">카메라</Text>
                            </TouchableOpacity>
                            <TouchableOpacity onPress={handleMic} className="items-center gap-2">
                                <View className="w-12 h-12 rounded-full bg-purple-500/20 items-center justify-center border border-purple-500/30">
                                    <MaterialIcons name="mic" size={24} color="#a855f7" />
                                </View>
                                <Text className="text-slate-300 text-xs font-medium">마이크</Text>
                            </TouchableOpacity>
                            <TouchableOpacity onPress={handleGallery} className="items-center gap-2">
                                <View className="w-12 h-12 rounded-full bg-emerald-500/20 items-center justify-center border border-emerald-500/30">
                                    <MaterialIcons name="photo-library" size={24} color="#10b981" />
                                </View>
                                <Text className="text-slate-300 text-xs font-medium">갤러리</Text>
                            </TouchableOpacity>
                        </View>
                    )}

                    <View className="flex-row items-center gap-3">
                        <TouchableOpacity
                            onPress={toggleMenu}
                            className={`w-10 h-10 rounded-full items-center justify-center ${isMenuOpen ? 'bg-white/20 rotate-45' : 'bg-surface-light active:bg-white/10'}`}
                        >
                            <MaterialIcons name={isMenuOpen ? "close" : "add"} size={26} color="white" />
                        </TouchableOpacity>

                        <View className="flex-1 flex-row items-center bg-surface-card rounded-full px-4 py-1 border border-white/10 shadow-lg">
                            <TextInput
                                className="flex-1 text-white py-3 text-[15px]"
                                placeholder={requestedAction === 'ANSWER_TEXT' ? "질문에 대한 답변을 입력하세요..." : "메시지를 입력하세요..."}
                                placeholderTextColor="#64748b"
                                value={userInput}
                                onChangeText={setUserInput}
                                multiline={false}
                                returnKeyType="send"
                                onFocus={() => useUIStore.getState().setKeyboardVisible(true)}
                                onSubmitEditing={handleSend}
                                blurOnSubmit={false}
                            />
                            <TouchableOpacity
                                onPress={handleSend}
                                className={`w-10 h-10 rounded-full items-center justify-center ${userInput.trim() ? 'bg-primary' : 'bg-surface-highlight'}`}
                                disabled={!userInput.trim()}
                            >
                                <MaterialIcons name="arrow-upward" size={22} color="white" />
                            </TouchableOpacity>
                        </View>
                    </View>
                </View>
            }
            padding={false}
            scrollable={false}
            androidKeyboardBehavior="height"
            useBottomNav={true}
        >
            <View className="flex-1 bg-background-dark">
                <ScrollView
                    ref={scrollRef}
                    className="flex-1 px-6 pt-4"
                    contentContainerStyle={{ paddingBottom: 20 }}
                    onContentSizeChange={() => scrollToEnd()}
                    onLayout={() => scrollToEnd()}
                    showsVerticalScrollIndicator={false}
                >
                    {messages.map((msg, idx) => (
                        <View
                            key={idx}
                            className={`mb-6 max-w-[85%] ${msg.role === 'user' ? 'self-end' : 'self-start'}`}
                        >
                            <View className={`p-4 rounded-2xl ${msg.role === 'user'
                                ? 'bg-primary rounded-tr-none'
                                : 'bg-surface-card border border-white/10 rounded-tl-none'
                                }`}>
                                <Text className="text-white text-[15px] leading-6">{msg.content}</Text>
                            </View>
                            <Text className="text-text-dim text-[10px] mt-1.5 px-1 font-medium italic">
                                {msg.role === 'user' ? '전송한 답변' : 'AI 분석가'}
                            </Text>
                        </View>
                    ))}

                    {/* Loading Indicator */}
                    {isWaitingForAi && (
                        <View className="mb-6 max-w-[85%] self-start">
                            <View className="p-4 rounded-2xl bg-surface-card border border-white/10 rounded-tl-none flex-row items-center gap-3 shadow-sm">
                                <ActivityIndicator size="small" color="#0d7ff2" />
                                <View className="flex-row items-center">
                                    <Text className="text-text-muted text-[15px] font-medium">AI가 답변을 준비 중입니다</Text>
                                    <DotPulse />
                                </View>
                            </View>
                        </View>
                    )}
                </ScrollView>
            </View>
        </BaseScreen>
    );
}
