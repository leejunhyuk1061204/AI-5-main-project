import React, { useState, useEffect, useRef } from 'react';
import { View, Text, TouchableOpacity, TextInput, Platform, Alert, Keyboard, ActivityIndicator, ScrollView } from 'react-native';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import BottomNav from '../nav/BottomNav';
import Header from '../header/Header';
import VehicleSelectModal from '../components/VehicleSelectModal';
import { diagnoseObdOnly, getDiagnosisSessionStatus, replyToDiagnosisSession } from '../api/aiApi';
import BaseScreen from '../components/layout/BaseScreen';
import { useUIStore } from '../store/useUIStore';

export default function AiProfessionalDiag() {
    const navigation = useNavigation<any>();
    const route = useRoute<any>();
    const insets = useSafeAreaInsets();

    // UI State
    const [mode, setMode] = useState<'IDLE' | 'PROCESSING' | 'INTERACTIVE' | 'REPORT'>('IDLE');
    const [messages, setMessages] = useState<any[]>([]);
    const [diagResult, setDiagResult] = useState<any>(null);
    const [loadingMessage, setLoadingMessage] = useState('차량 진단 중...');
    const [userInput, setUserInput] = useState('');
    const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
    const [vehicleSelectVisible, setVehicleSelectVisible] = useState(false);
    const [selectedVehicleId, setSelectedVehicleId] = useState<string | null>(null);
    const [selectedVehicleName, setSelectedVehicleName] = useState<string | null>(null);
    const [pendingAction, setPendingAction] = useState<'OBD' | 'SOUND' | 'PHOTO' | null>(null);
    const [isWaitingForAi, setIsWaitingForAi] = useState(false);
    const isKeyboardVisible = useUIStore(state => state.isKeyboardVisible);
    const scrollRef = useRef<ScrollView>(null);

    // Auto-scroll logic
    const scrollToEnd = (animated = false) => {
        scrollRef.current?.scrollToEnd({ animated });
    };

    // Logic Implementation

    // Logic Implementation
    const handleVehicleSelect = async (vehicle: any) => {
        setVehicleSelectVisible(false);
        setSelectedVehicleId(vehicle.vehicleId);
        setSelectedVehicleName(`${vehicle.modelNameKo} (${vehicle.carNumber})`);

        // Dispatch action based on pendingAction
        if (pendingAction === 'OBD') {
            await startObdDiagnosis(vehicle.vehicleId);
        } else if (pendingAction === 'SOUND') {
            navigation.navigate('EngineSoundDiag', {
                from: 'professional',
                vehicleId: vehicle.vehicleId,
                sessionId: currentSessionId
            });
        } else if (pendingAction === 'PHOTO') {
            navigation.navigate('Filming', {
                from: 'professional',
                vehicleId: vehicle.vehicleId,
                sessionId: currentSessionId
            });
        }
        setPendingAction(null);
    };

    const startObdDiagnosis = async (vehicleId: string) => {
        try {
            setMode('PROCESSING');
            setLoadingMessage('차량 데이터를 분석하고 있습니다...');

            // OBD Only Diagnosis
            const response = await diagnoseObdOnly(vehicleId);

            // Fix: Access sessionId from data property if response is wrapped
            const sessionId = response?.sessionId;

            if (sessionId) {
                setCurrentSessionId(sessionId);
                // Polling will start via useEffect
            } else {
                Alert.alert("알림", "진단 세션이 생성되지 않았습니다.");
                setMode('IDLE');
            }
        } catch (error) {
            console.error("Diagnosis Start Error:", error);
            Alert.alert("오류", "진단을 시작하는 중 문제가 발생했습니다.");
            setMode('IDLE');
        }
    };

    const handleSendReply = async () => {
        if (!userInput.trim() || !currentSessionId || !selectedVehicleId) return;

        try {
            const reply = userInput;
            setUserInput(''); // Clear input immediately

            // 1. UI 피드백: 메시지 목록에 즉시 추가
            setMessages(prev => [...prev, { role: 'user', content: reply }]);

            // 2. AI 답변 대기 상태로 전환 (채팅창 유지)
            setIsWaitingForAi(true);

            // Send reply
            await replyToDiagnosisSession(currentSessionId, {
                vehicleId: selectedVehicleId,
                userResponse: reply
            });
            // Status will be updated by polling (will eventually return to INTERACTIVE or REPORT)
        } catch (error) {
            console.error("Reply Error:", error);
            Alert.alert("오류", "답변 전송에 실패했습니다.");
            setIsWaitingForAi(false);
        }
    };

    const handleFinishDiagnosis = () => {
        setMessages([]);
        setCurrentSessionId(null);
        setDiagResult(null);
        setUserInput('');
        setMode('IDLE');
    };

    // Handle returned diagnosis results from Photo/Sound pages
    useEffect(() => {
        if (route.params?.diagnosisResult) {
            const result = route.params.diagnosisResult;
            const newMsg = {
                role: 'ai',
                content: `진단이 완료되었습니다.\n결과: ${result.result === 'NORMAL' ? '정상' : '이상 감지'}\n\n${result.description}`,
                isResult: true
            };
            setMessages(prev => [...prev, newMsg]);

            // If the user was in IDLE or PROCESSING, move to INTERACTIVE to show the chat
            if (mode === 'IDLE' || mode === 'PROCESSING') {
                setMode('INTERACTIVE');
            }

            // Clear params to avoid duplicate messages on re-render
            navigation.setParams({ diagnosisResult: null });
        }
    }, [route.params?.diagnosisResult]);

    // Polling Effect (1분 타임아웃 적용)
    useEffect(() => {
        let intervalId: NodeJS.Timeout;
        const startTime = Date.now();

        if ((mode === 'PROCESSING' || mode === 'INTERACTIVE') && currentSessionId) {
            intervalId = setInterval(async () => {
                const elapsed = Date.now() - startTime;
                if (elapsed > 60000) { // 1분 초과 시
                    console.warn('[AiProfessionalDiag] Polling Timeout (1min)');
                    clearInterval(intervalId);
                    setMode('IDLE');
                    setIsWaitingForAi(false);
                    Alert.alert('알림', '진단 시간이 초과되었습니다. 현재 연결 상태를 확인해주세요.');
                    return;
                }

                try {
                    const statusData = await getDiagnosisSessionStatus(currentSessionId);

                    if (statusData) {
                        // Update Messages if available

                        const currentStatus = (statusData.status || '').toUpperCase();

                        // Sync messages from interactiveData
                        if (statusData.interactiveData) {
                            const newMessages = [];
                            if (statusData.interactiveData.conversation) {
                                newMessages.push(...statusData.interactiveData.conversation);
                            }
                            if (statusData.interactiveData.message) {
                                const lastMsg = newMessages[newMessages.length - 1];
                                if (!lastMsg || lastMsg.content !== statusData.interactiveData.message) {
                                    newMessages.push({ role: 'ai', content: statusData.interactiveData.message });
                                }
                            }
                            if (newMessages.length > 0) setMessages(newMessages);
                        }

                        // Check Status
                        if (currentStatus === 'INTERACTIVE' || currentStatus === 'ACTION_REQUIRED') {
                            if (mode !== 'INTERACTIVE') setMode('INTERACTIVE');
                            setIsWaitingForAi(false);
                        } else if (currentStatus === 'REPORT' || currentStatus === 'DONE' || currentStatus === 'COMPLETED' || currentStatus === 'SUCCESS') {
                            setMode('REPORT');
                            setIsWaitingForAi(false);
                            setDiagResult(statusData.report || statusData.result || statusData);
                            clearInterval(intervalId);
                        } else if (currentStatus === 'PROCESSING') {
                            // Update loading message with progress if available
                            if (statusData.progressMessage) {
                                setLoadingMessage(statusData.progressMessage);
                            }
                        }
                    }
                } catch (e) {
                    console.error("Polling Error:", e);
                }
            }, 2000); // Poll every 2 seconds
        }

        return () => {
            if (intervalId) clearInterval(intervalId);
        };
    }, [mode, currentSessionId]);

    // Auto-scroll to bottom when messages change
    useEffect(() => {
        if (mode === 'INTERACTIVE') {
            scrollToEnd(false);
        }
    }, [messages, mode]);

    const ActionButton = ({ icon, label, onPress, color = "#3b82f6", disabled = false }: { icon: any, label: string, onPress: () => void, color?: string, disabled?: boolean }) => (
        <TouchableOpacity
            onPress={onPress}
            disabled={disabled}
            className={`flex-1 bg-[#1e293b] border border-white/10 rounded-2xl p-4 items-center justify-center active:scale-95 ${disabled ? 'opacity-50' : ''}`}
            style={{ height: 110 }}
        >
            <View className="w-12 h-12 rounded-xl items-center justify-center mb-2" style={{ backgroundColor: `${color}20` }}>
                {label === "OBD 스캔" ? (
                    <MaterialCommunityIcons name={icon} size={28} color={color} />
                ) : (
                    <MaterialIcons name={icon} size={28} color={color} />
                )}
            </View>
            <Text className="text-white font-bold text-[13px]">{label}</Text>
            {!disabled && <View className="absolute bottom-0 left-0 right-0 h-1 rounded-b-2xl" style={{ backgroundColor: color }} />}
        </TouchableOpacity>
    );

    const handleFocus = () => {
        // 즉각적인 하단바 숨김 트리거
        useUIStore.getState().setKeyboardVisible(true);
    };

    return (
        <BaseScreen
            header={<Header />}
            scrollable={false}
            androidKeyboardBehavior="height"
            footer={
                <View className="w-full">
                    {/* Vehicle Selection Modal */}
                    <VehicleSelectModal
                        visible={vehicleSelectVisible}
                        onClose={() => setVehicleSelectVisible(false)}
                        onSelect={handleVehicleSelect}
                        description="진단을 진행할 차량을 선택해주세요."
                    />

                    {/* Interactive Input Area */}
                    {mode === 'INTERACTIVE' && (
                        <View
                            className="px-6 py-4 bg-[#101922] border-t border-white/5"
                            style={{
                                minHeight: 80, // 최소 높이 확보
                            }}
                        >
                            <View className="flex-row items-center bg-[#1e293b] rounded-full px-4 py-1 border border-white/10 shadow-lg">
                                <TextInput
                                    className="flex-1 text-white py-3 text-[15px]"
                                    placeholder="질문에 답변을 입력하세요..."
                                    placeholderTextColor="#64748b"
                                    value={userInput}
                                    onChangeText={setUserInput}
                                    multiline={false}
                                    returnKeyType="send"
                                    onFocus={handleFocus}
                                    onSubmitEditing={handleSendReply}
                                />
                                <TouchableOpacity
                                    onPress={handleSendReply}
                                    className={`w-10 h-10 rounded-full items-center justify-center ${userInput.trim() ? 'bg-primary' : 'bg-slate-700'}`}
                                    disabled={!userInput.trim()}
                                >
                                    <MaterialIcons name="arrow-upward" size={22} color="white" />
                                </TouchableOpacity>
                            </View>
                        </View>
                    )}
                </View>
            }
            useBottomNav={true} // 탭 메뉴로 쓰일 때 하단바 여백 확보
        >
            <View className="flex-1 mt-4">
                {/* 1. Vehicle Info Card */}
                <TouchableOpacity
                    onPress={() => mode === 'IDLE' && setVehicleSelectVisible(true)}
                    className="bg-[#1e293b] rounded-2xl p-5 mb-8 border border-white/10 shadow-sm"
                >
                    <View className="flex-row items-center gap-4">
                        <View className="w-12 h-12 bg-primary/20 rounded-xl items-center justify-center">
                            <MaterialIcons name="directions-car" size={24} color="#3b82f6" />
                        </View>
                        <View className="flex-1">
                            <Text className="text-white/50 text-xs font-medium mb-0.5">진단 대상 차량</Text>
                            <Text className="text-white text-lg font-bold">
                                {selectedVehicleName || '차량을 선택해주세요'}
                            </Text>
                        </View>
                    </View>
                </TouchableOpacity>

                {/* 2. Diagnosis Modes Grid */}
                {mode === 'IDLE' && (
                    <View className="flex-row gap-3">
                        <ActionButton
                            icon="engine-outline"
                            label="OBD 스캔"
                            color="#3b82f6"
                            onPress={() => {
                                if (selectedVehicleId) {
                                    startObdDiagnosis(selectedVehicleId);
                                } else {
                                    setPendingAction('OBD');
                                    setVehicleSelectVisible(true);
                                }
                            }}
                        />
                        <ActionButton
                            icon="photo-camera"
                            label="사진 진단"
                            color="#3b82f6"
                            onPress={() => {
                                if (selectedVehicleId) {
                                    navigation.navigate('Filming', {
                                        from: 'professional',
                                        vehicleId: selectedVehicleId,
                                        sessionId: currentSessionId
                                    });
                                } else {
                                    setPendingAction('PHOTO');
                                    setVehicleSelectVisible(true);
                                }
                            }}
                        />
                        <ActionButton
                            icon="bluetooth-audio"
                            label="소리 진단"
                            color="#3b82f6"
                            onPress={() => {
                                if (selectedVehicleId) {
                                    navigation.navigate('EngineSoundDiag', {
                                        from: 'professional',
                                        vehicleId: selectedVehicleId,
                                        sessionId: currentSessionId
                                    });
                                } else {
                                    setPendingAction('SOUND');
                                    setVehicleSelectVisible(true);
                                }
                            }}
                        />
                    </View>
                )}

                {/* Processing State */}
                {mode === 'PROCESSING' && (
                    <View className="bg-[#1e293b] rounded-2xl p-8 border border-white/10 items-center justify-center">
                        <ActivityIndicator size="large" color="#3b82f6" className="mb-4" />
                        <Text className="text-white font-bold text-lg mb-2">{loadingMessage}</Text>
                        <Text className="text-slate-400 text-center">AI가 차량 데이터를 분석 중입니다. 잠시만 기다려주세요.</Text>
                    </View>
                )}

                {/* Interactive State (Chat) */}
                {mode === 'INTERACTIVE' && (
                    <ScrollView
                        ref={scrollRef}
                        className="flex-1"
                        contentContainerStyle={{ paddingBottom: 40 }}
                        onContentSizeChange={() => scrollToEnd()}
                        onLayout={() => scrollToEnd()}
                        showsVerticalScrollIndicator={false}
                    >
                        {messages.map((msg, idx) => (
                            <View
                                key={idx}
                                className={`mb-4 max-w-[85%] ${msg.role === 'user' ? 'self-end' : 'self-start'}`}
                            >
                                <View className={`p-4 rounded-2xl ${msg.role === 'user' ? 'bg-[#3b82f6] rounded-tr-none' : 'bg-[#1e293b] border border-white/10 rounded-tl-none'}`}>
                                    <Text className="text-white text-[15px] leading-6">{msg.content}</Text>
                                </View>
                                <Text className="text-slate-500 text-[10px] mt-1 px-1">
                                    {msg.role === 'user' ? '나' : 'AI 전문 분석가'}
                                </Text>
                            </View>
                        ))}

                        {/* Thinking Indicator (Loading Bubble) */}
                        {isWaitingForAi && (
                            <View className="mb-4 max-w-[85%] self-start">
                                <View className="p-4 rounded-2xl bg-[#1e293b] border border-white/10 rounded-tl-none flex-row items-center gap-2">
                                    <ActivityIndicator size="small" color="#3b82f6" />
                                    <Text className="text-slate-400 text-sm">AI가 분석 중입니다...</Text>
                                </View>
                            </View>
                        )}

                        {/* If messages is empty but in interactive mode, show a loading for the first message */}
                        {messages.length === 0 && !isWaitingForAi && (
                            <ActivityIndicator size="small" color="#3b82f6" />
                        )}
                    </ScrollView>
                )}

                {/* Report State */}
                {mode === 'REPORT' && diagResult && (
                    <ScrollView className="flex-1" showsVerticalScrollIndicator={false}>
                        <View className="bg-[#1e293b] rounded-3xl p-6 border border-white/10 mb-6">
                            <View className="flex-row items-center gap-3 mb-4">
                                <View className="w-10 h-10 bg-green-500/20 rounded-full items-center justify-center">
                                    <MaterialIcons name="fact-check" size={24} color="#22c55e" />
                                </View>
                                <Text className="text-white text-xl font-bold">진단 분석 결과</Text>
                            </View>

                            <Text className="text-slate-400 text-sm leading-6 mb-6">
                                {diagResult.summary || '종합 분석이 완료되었습니다.'}
                            </Text>

                            <View className="bg-white/5 rounded-2xl p-5 border border-white/5">
                                <Text className="text-primary font-bold mb-3">🛠️ 주요 권장 사항</Text>
                                <Text className="text-white leading-7 text-[15px]">
                                    {diagResult.finalReport}
                                </Text>
                            </View>

                            <TouchableOpacity
                                className="mt-8 bg-[#3b82f6] py-4 rounded-2xl items-center shadow-lg shadow-blue-500/20"
                                onPress={handleFinishDiagnosis}
                            >
                                <Text className="text-white font-bold text-base">확인 완료</Text>
                            </TouchableOpacity>
                        </View>
                    </ScrollView>
                )}

                {/* Input Area was here - Removed as it's now in footer prop */}
            </View>
        </BaseScreen>
    );
}
