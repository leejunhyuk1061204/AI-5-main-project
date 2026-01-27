import React, { useState, useEffect, useRef } from 'react';
import { View, Text, TouchableOpacity, TextInput, ActivityIndicator, ScrollView, Platform, Keyboard } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import Header from '../header/Header';
import BaseScreen from '../components/layout/BaseScreen';
import { useAiDiagnosisStore } from '../store/useAiDiagnosisStore';
import { useUIStore } from '../store/useUIStore';

export default function AiDiagChat() {
    const navigation = useNavigation<any>();
    const route = useRoute<any>();
    const scrollRef = useRef<ScrollView>(null);
    const [userInput, setUserInput] = useState('');

    const {
        status,
        messages,
        sendReply,
        updateStatus,
        currentSessionId,
        isWaitingForAi,
        reset
    } = useAiDiagnosisStore();

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
        if ((status === 'INTERACTIVE' || status === 'ACTION_REQUIRED' || isWaitingForAi) && currentSessionId) {
            intervalId = setInterval(() => {
                updateStatus(currentSessionId);
            }, 2000);
        }
        return () => {
            if (intervalId) clearInterval(intervalId);
        };
    }, [status, currentSessionId, isWaitingForAi]);

    // Status Watcher: 리포트 완료 시 이동
    useEffect(() => {
        if (status === 'REPORT') {
            navigation.navigate('DiagnosisReport', { sessionId: currentSessionId });
        }
    }, [status]);

    const handleSend = async () => {
        if (!userInput.trim()) return;
        const msg = userInput;
        setUserInput('');
        await sendReply(msg);
    };

    const handleFocus = () => {
        // 즉각적인 하단바 숨김 트리거 (전문가 페이지와 동일)
        useUIStore.getState().setKeyboardVisible(true);
    };

    const renderInputArea = () => (
        <View
            className="px-6 py-4 bg-background-dark border-t border-white/5"
            style={{ minHeight: 80 }}
        >
            <View className="flex-row items-center bg-surface-card rounded-full px-4 py-1 border border-white/10 shadow-lg">
                <TextInput
                    className="flex-1 text-white py-3 text-[15px]"
                    placeholder="질문에 답변을 입력하세요..."
                    placeholderTextColor="#64748b"
                    value={userInput}
                    onChangeText={setUserInput}
                    multiline={false}
                    returnKeyType="send"
                    onFocus={handleFocus}
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
    );

    return (
        <BaseScreen
            header={<Header />}
            footer={renderInputArea()}
            padding={false}
            scrollable={false}
            androidKeyboardBehavior="height"
            useBottomNav={true} // 키보드 활성화 시 하단 영역 자동 수축 로직 활용
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

                    {isWaitingForAi && (
                        <View className="mb-6 max-w-[85%] self-start">
                            <View className="p-4 rounded-2xl bg-surface-card border border-white/10 rounded-tl-none flex-row items-center gap-3">
                                <ActivityIndicator size="small" color="#0d7ff2" />
                                <Text className="text-text-muted text-sm font-medium">AI가 답변을 준비 중입니다...</Text>
                            </View>
                        </View>
                    )}
                </ScrollView>
            </View>
        </BaseScreen>
    );
}
