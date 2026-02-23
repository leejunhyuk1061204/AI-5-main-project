import React, { useState, useEffect, useRef, useCallback } from 'react';
import { View, Text, TouchableOpacity, TextInput, ActivityIndicator, ScrollView, Animated, Platform, StyleSheet, KeyboardAvoidingView, Keyboard, Image } from 'react-native';
import { useNavigation, useRoute, RouteProp, useFocusEffect } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons } from '@expo/vector-icons';

// Global Stores
import { useUIStore } from '../store/useUIStore';
import { useVehicleStore } from '../store/useVehicleStore';
import { useUserStore } from '../store/useUserStore';
import { useBleStore } from '../store/useBleStore';

// API
import { getDiagnosisSessionStatus, replyToDiagnosisSession, AiDiagnosisResponse, DiagnosisMessage } from '../api/aiApi';
import Header from '../header/Header';
import { DiagType, useAiDiagnosisStore } from '../store/useAiDiagnosisStore';
import { useAlertStore } from '../store/useAlertStore';

// Types
type RootStackParamList = {
    Login: undefined;
    AlertMain: undefined;
    Filming: { sessionId: string | null; vehicleId?: number; diagType?: DiagType };
    EngineSoundDiag: { sessionId: string | null; vehicleId?: number; diagType?: DiagType };
    DiagnosisReport: { sessionId: string; reportData: any; diagType?: DiagType };
    AiDiagChat: { autoStart?: boolean; vehicleId?: string; sessionId?: string; pendingMessage?: { type: 'image' | 'audio'; uri: string; text: string; timestamp: number }; diagType?: DiagType };
    ChatCameraScreen: { sessionId: string | null; vehicleId?: string; diagType?: DiagType };
    ChatAudioScreen: { sessionId: string | null; vehicleId?: string; diagType?: DiagType };
    MainHome: undefined;
    DiagTab: undefined;
    HistoryTab: undefined;
    SettingTab: undefined;
};



/**
 * SIMPLE BOTTOM NAV (Recreated Locally)
 */
const SimpleBottomNav = ({ onNavigate, currentParams }: { onNavigate: (screen: keyof RootStackParamList) => void, currentParams?: any }) => {
    const insets = useSafeAreaInsets();

    const tabs = [
        { key: 'MainHome', label: '홈', icon: 'home' },
        { key: 'DiagTab', label: '진단', icon: 'car-crash' },
        { key: 'HistoryTab', label: '기록', icon: 'history' },
        { key: 'SettingTab', label: '설정', icon: 'settings' },
    ];

    const activeTab = 'DiagTab'; // Always active since we are in Diag

    return (
        <View style={[styles.navContainer, { paddingBottom: insets.bottom }]}>
            <View style={styles.navContent}>
                {tabs.map((tab) => {
                    const isActive = tab.key === activeTab;
                    return (
                        <TouchableOpacity
                            key={tab.key}
                            style={styles.navItem}
                            onPress={() => onNavigate(tab.key as keyof RootStackParamList)}
                            activeOpacity={0.7}
                        >
                            <MaterialIcons
                                name={tab.icon as any}
                                size={24}
                                color={isActive ? '#0d7ff2' : '#6b7280'}
                            />
                            <Text style={[styles.navLabel, isActive ? styles.navLabelActive : styles.navLabelInactive]}>
                                {tab.label}
                            </Text>
                            {isActive && <View style={styles.navIndicator} />}
                        </TouchableOpacity>
                    );
                })}
            </View>
        </View>
    );
};


/**
 * DOT PULSE ANIMATION
 */
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
        <View style={styles.dotContainer}>
            <Animated.Text style={[styles.dot, { opacity: dot1 }]}>.</Animated.Text>
            <Animated.Text style={[styles.dot, { opacity: dot2 }]}>.</Animated.Text>
            <Animated.Text style={[styles.dot, { opacity: dot3 }]}>.</Animated.Text>
        </View>
    );
};

/**
 * MAIN COMPONENT: AiDiagChat (Refactored)
 */
export default function AiDiagChat() {
    console.log('[AiDiagChat] Rendered: StyleSheet + UseNavigation + KAV + SimpleBottomNav');

    // Navigation Hooks
    const navigation = useNavigation<any>();
    const route = useRoute<RouteProp<RootStackParamList, 'AiDiagChat'>>();

    // Layout Refs
    const insets = useSafeAreaInsets();
    const scrollRef = useRef<ScrollView>(null);

    // State
    const [userInput, setUserInput] = useState('');
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const [sessionData, setSessionData] = useState<AiDiagnosisResponse | null>(null);
    const [messages, setMessages] = useState<DiagnosisMessage[]>([]);
    const [loading, setLoading] = useState(false);
    const [isWaitingForAi, setIsWaitingForAi] = useState(false);

    // Stores (UI만 사용)
    const { primaryVehicle } = useVehicleStore();
    const { isKeyboardVisible, setKeyboardVisible } = useUIStore();
    const { nickname, loadUser } = useUserStore();
    const { status: bleStatus } = useBleStore();
    // sessionId 추출 (route params 우선)
    const sessionId = route.params?.sessionId || null;
    const diagType: DiagType = route.params?.diagType || 'OBD';

    // Global diagnosis store (for syncing overall session state on failure + REPORT 시 즉시 이동)
    const { reset } = useAiDiagnosisStore();
    const storeStatus = useAiDiagnosisStore(state => state.sessions[diagType]?.status);
    const storeDiagResult = useAiDiagnosisStore(state => state.sessions[diagType]?.diagResult);

    // -- EFFECTS --
    useEffect(() => { loadUser(); }, []);

    // 채팅에서 뒤로가기 시 해당 타입을 IDLE로 → 진단 메인에서 새 진단 가능, 이어하기는 진단 내역에서만
    useEffect(() => {
        const unsub = navigation.addListener('beforeRemove', (e: any) => {
            const action = e.data?.action;
            if (action?.type === 'POP' || action?.type === 'GO_BACK') {
                reset(diagType);
            }
        });
        return unsub;
    }, [navigation, reset, diagType]);

    // store가 REPORT로 바뀌면 (예: OBD step5 후) 채팅에 머물지 않고 바로 리포트로 이동
    useEffect(() => {
        if (storeStatus !== 'REPORT' || !sessionId) return;
        const reportData = storeDiagResult ?? sessionData ?? undefined;
        navigation.replace('DiagnosisReport', { sessionId, reportData, diagType });
    }, [storeStatus, sessionId, storeDiagResult, sessionData, diagType]);

    // 세션 데이터 로드 함수
    const loadSessionData = async (sid: string) => {
        if (!sid) return;
        setLoading(true);
        try {
            const data = await getDiagnosisSessionStatus(sid);
            setSessionData(data);

            // 1. 메시지 추출
            let msgs: any[] = [];
            if (data.interactiveData?.conversation) {
                msgs = data.interactiveData.conversation;
            }
            // AI의 마지막 메시지 추가 (서버 API 응답 구조 준수)
            // AI의 마지막 메시지 추가 (서버 API 응답 구조 준수)
            if (data.interactiveData?.message) {
                // 중복 방지: 서버가 보낸 메시지가 이미 대화 목록(특히 끝부분)에 있는지 확인
                const isMessageAlreadyExist = msgs.some((m, idx) =>
                    idx >= msgs.length - 2 && m.role === 'ai' && m.content === data.interactiveData?.message
                );

                if (!isMessageAlreadyExist) {
                    msgs.push({ role: 'ai', content: data.interactiveData.message });
                }
            }

            // 2. 서버에서 온 메시지들 (isPending 없음)
            const serverMsgs = msgs.map((m: DiagnosisMessage) => ({ ...m, isPending: false }));

            // 3. 현재 로컬 상태에서 아직 서버에 반영 안 된(펜딩 중인) 사용자 메시지 추출
            // (서버 메시지와 내용이 겹치지 않는 것만 유지)
            setMessages((prev: DiagnosisMessage[]) => {
                const pendingMsgs = prev.filter(m => m.isPending);
                const filteredPending = pendingMsgs.filter(p =>
                    !serverMsgs.some((s: DiagnosisMessage) => s.role === 'user' && s.content === p.content)
                );
                return [...serverMsgs, ...filteredPending];
            });

            // 대기 상태 업데이트
            const isProcessing = data.status === 'PROCESSING' || data.status === 'REPLY_PROCESSING';
            setIsWaitingForAi(isProcessing);

            // 완료 시 리포트 화면으로 이동
            if (data.status === 'DONE' || data.status === 'COMPLETED' || data.responseMode === 'REPORT' || data.response_mode === 'REPORT') {
                console.log("[AiDiagChat] Diagnosis COMPLETED. Navigating to Report.");
                navigation.replace('DiagnosisReport', {
                    sessionId: sid,
                    reportData: data,
                    diagType
                });
            }

            // FAILED 상태 처리 (알림 표시 + 글로벌 세션 상태 리셋)
            if (data.status === 'FAILED' || data.status === 'ERROR') {
                console.log("[AiDiagChat] Diagnosis FAILED. Showing error message and resetting session state.");
                // 전역 진단 세션 상태 초기화 (해당 diagType만)
                reset(diagType);
                useAlertStore.getState().showAlert(
                    '진단 실패',
                    data.progressMessage || 'AI 분석 중 문제가 발생했습니다. 다시 시도해 주세요.',
                    'ERROR',
                    () => navigation.goBack()
                );
            }
        } catch (error) {
            console.error('[AiDiagChat] Failed to load session:', error);
        } finally {
            setLoading(false);
        }
    };

    // sessionId가 있으면 세션 데이터 로드 (초기 진입 & 화면 포커스 시)
    useFocusEffect(
        useCallback(() => {
            // 1. pendingMessage가 있으면 즉시 표시 (Optimistic UI)
            if (route.params?.pendingMessage) {
                const pending = route.params.pendingMessage;
                const newMessage: DiagnosisMessage = {
                    role: 'user',
                    content: pending.text,
                    mediaType: pending.type,
                    mediaUri: pending.uri,
                    timestamp: pending.timestamp,
                    isPending: true
                };

                setMessages(prev => {
                    // 중복 방지: 같은 timestamp의 메시지가 없으면 추가
                    const exists = prev.some(m => m.timestamp === pending.timestamp);
                    if (!exists) {
                        return [...prev, newMessage];
                    }
                    return prev;
                });

                // params 클리어하여 중복 방지
                navigation.setParams({ pendingMessage: undefined } as any);

                // 대기 상태 설정
                setIsWaitingForAi(true);
            }

            // 2. 세션 데이터 로드
            if (sessionId) {
                loadSessionData(sessionId);
            }
        }, [sessionId, route.params?.pendingMessage])
    );

    // 폴링 (진행 중일 때만 - 1분 타임아웃 적용)
    useEffect(() => {
        if (!sessionId || !sessionData) return;

        const shouldPoll = sessionData.status === 'PROCESSING' || sessionData.status === 'REPLY_PROCESSING' || isWaitingForAi;
        if (!shouldPoll) return;

        const startTime = Date.now();
        const intervalId = setInterval(() => {
            const elapsed = Date.now() - startTime;
            if (elapsed > 60000) { // 1분 초과 시
                console.warn('[AiDiagChat] Polling Timeout (1min)');
                clearInterval(intervalId);
                setIsWaitingForAi(false);
                useAlertStore.getState().showAlert('알림', '진단 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.', 'WARNING');
                return;
            }
            loadSessionData(sessionId);
        }, 3000);

        return () => clearInterval(intervalId);
    }, [sessionId, sessionData?.status, isWaitingForAi]);

    // Auto-Scroll
    const scrollToBottom = (animated = true) => {
        scrollRef.current?.scrollToEnd({ animated });
    };

    useEffect(() => {
        const timer = setTimeout(() => scrollToBottom(), 100);
        return () => clearTimeout(timer);
    }, [messages, isWaitingForAi]);

    // Keyboard Listeners (Optional backup if store fails, but store should work)
    useEffect(() => {
        const showSubscription = Keyboard.addListener('keyboardDidShow', () => setKeyboardVisible(true));
        const hideSubscription = Keyboard.addListener('keyboardDidHide', () => setKeyboardVisible(false));
        return () => {
            showSubscription.remove();
            hideSubscription.remove();
        };
    }, []);


    // -- HANDLERS --
    const handleSend = async () => {
        if (!userInput.trim() || !sessionId) return;

        const msg = userInput;
        setUserInput('');

        // 즉시 UI 반영 (timestamp와 isPending 추가)
        const timestamp = Date.now();
        const newUserMsg: DiagnosisMessage = {
            role: 'user',
            content: msg,
            timestamp,
            isPending: true
        };
        setMessages(prev => [...prev, newUserMsg]);
        setIsWaitingForAi(true);

        try {
            await replyToDiagnosisSession(sessionId, {
                vehicleId: route.params?.vehicleId || primaryVehicle?.vehicleId || '',
                userResponse: msg
            });

            // 답변 후 세션 상태 새로고침
            await loadSessionData(sessionId);
        } catch (error) {
            console.error('[AiDiagChat] Reply failed:', error);
            setIsWaitingForAi(false);
        }
    };

    const handleCamera = () => {
        setIsMenuOpen(false);
        navigation.navigate('ChatCameraScreen', { sessionId, vehicleId: route.params?.vehicleId, diagType });
    };

    const handleMic = () => {
        setIsMenuOpen(false);
        navigation.navigate('ChatAudioScreen', { sessionId, vehicleId: route.params?.vehicleId, diagType });
    };

    const handleGallery = () => {
        setIsMenuOpen(false);
        navigation.navigate('Filming', { sessionId, vehicleId: route.params?.vehicleId, diagType });
    };

    const onNavigate = (screen: keyof RootStackParamList) => {
        navigation.navigate(screen);
    };

    const onBack = () => {
        reset(diagType);
        navigation.goBack();
    };


    // -- RENDER --
    return (
        <View style={styles.container}>
            <StatusBar style="light" />

            {/* Header */}
            <View style={{ paddingTop: insets.top }}>
                <Header />
            </View>

            {/* Main Content with Keyboard Handling */}
            <KeyboardAvoidingView
                style={{ flex: 1 }}
                behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
            >

                <View style={[styles.chatContainer, { paddingBottom: isKeyboardVisible ? 0 : 0 }]}>
                    <ScrollView
                        ref={scrollRef}
                        style={styles.scrollView}
                        contentContainerStyle={styles.scrollContent}
                        onContentSizeChange={() => scrollToBottom()}
                        onLayout={() => scrollToBottom()}
                        showsVerticalScrollIndicator={false}
                    >
                        {messages.map((msg, idx) => (
                            <View
                                key={idx}
                                style={[
                                    styles.messageWrapper,
                                    msg.role === 'user' ? styles.messageUser : styles.messageAi
                                ]}
                            >
                                <View style={[
                                    styles.messageBubble,
                                    msg.role === 'user' ? styles.bubbleUser : styles.bubbleAi
                                ]}>
                                    {/* 이미지 미리보기 */}
                                    {msg.mediaType === 'image' && msg.mediaUri && (
                                        <Image
                                            source={{ uri: msg.mediaUri }}
                                            style={styles.mediaPreview}
                                            resizeMode="cover"
                                        />
                                    )}

                                    {/* 오디오 파일 표시 */}
                                    {msg.mediaType === 'audio' && msg.mediaUri && (
                                        <View style={styles.audioPreview}>
                                            <MaterialIcons name="audiotrack" size={20} color="#0d7ff2" />
                                            <Text style={styles.audioFileName}>오디오 녹음.m4a</Text>
                                        </View>
                                    )}

                                    <Text style={styles.messageText}>{msg.content}</Text>

                                    {/* pending 표시 */}
                                    {msg.isPending && (
                                        <Text style={styles.pendingIndicator}>전송 중...</Text>
                                    )}
                                </View>
                                <Text style={styles.messageMeta}>
                                    {msg.role === 'user' ? '전송한 답변' : 'AI 분석가'}
                                </Text>
                            </View>
                        ))}

                        {/* Loading State */}
                        {isWaitingForAi && (
                            <View style={[styles.messageWrapper, styles.messageAi]}>
                                <View style={[styles.messageBubble, styles.bubbleAi, styles.loadingBubble]}>
                                    <ActivityIndicator size="small" color="#0d7ff2" />
                                    <View style={styles.loadingTextWrapper}>
                                        <Text style={styles.loadingText}>
                                            {messages.filter(m => m.role === 'user').length >= 3
                                                ? "AI가 진단 결과를 생성 중입니다"
                                                : "AI가 답변을 준비 중입니다"}
                                        </Text>
                                        <DotPulse />
                                    </View>
                                </View>
                            </View>
                        )}
                    </ScrollView>

                    {/* Input Area */}
                    <View style={[styles.inputArea, { paddingBottom: !isKeyboardVisible ? 16 : 16 }]}>

                        {/* Dynamic Action Buttons */}
                        {sessionData?.requestedAction && !isWaitingForAi && (
                            <View style={styles.actionButtonsContainer}>
                                {sessionData.requestedAction === 'CAPTURE_PHOTO' && (
                                    <TouchableOpacity onPress={handleCamera} style={[styles.actionButton, styles.actionButtonPrimary]}>
                                        <MaterialIcons name="photo-camera" size={18} color="#0d7ff2" />
                                        <Text style={styles.actionButtonTextPrimary}>사진 촬영하기</Text>
                                    </TouchableOpacity>
                                )}
                                {sessionData.requestedAction === 'RECORD_AUDIO' && (
                                    <TouchableOpacity onPress={handleMic} style={[styles.actionButton, styles.actionButtonSecondary]}>
                                        <MaterialIcons name="mic" size={18} color="#a855f7" />
                                        <Text style={styles.actionButtonTextSecondary}>소리 녹음하기</Text>
                                    </TouchableOpacity>
                                )}
                            </View>
                        )}

                        {/* Menu */}
                        {isMenuOpen && (
                            <View style={styles.menuArea}>
                                <TouchableOpacity onPress={handleCamera} style={styles.menuItem}>
                                    <View style={[styles.menuIconCircle, styles.menuIconBlue]}>
                                        <MaterialIcons name="camera-alt" size={24} color="#3b82f6" />
                                    </View>
                                    <Text style={styles.menuText}>카메라</Text>
                                </TouchableOpacity>
                                <TouchableOpacity onPress={handleMic} style={styles.menuItem}>
                                    <View style={[styles.menuIconCircle, styles.menuIconPurple]}>
                                        <MaterialIcons name="mic" size={24} color="#a855f7" />
                                    </View>
                                    <Text style={styles.menuText}>마이크</Text>
                                </TouchableOpacity>
                                {/*<TouchableOpacity onPress={handleGallery} style={styles.menuItem}>
                                    <View style={[styles.menuIconCircle, styles.menuIconEmerald]}>
                                        <MaterialIcons name="photo-library" size={24} color="#10b981" />
                                    </View>
                                    <Text style={styles.menuText}>갤러리</Text>
                                </TouchableOpacity>*/}
                            </View>
                        )}

                        {/* Input Bar */}
                        <View style={styles.inputRow}>
                            <TouchableOpacity
                                onPress={() => setIsMenuOpen(!isMenuOpen)}
                                style={[styles.plusButton, isMenuOpen ? styles.plusButtonActive : styles.plusButtonInactive]}
                            >
                                <MaterialIcons name={isMenuOpen ? "close" : "add"} size={26} color="white" />
                            </TouchableOpacity>

                            <View style={styles.inputWrapper}>
                                <TextInput
                                    style={styles.textInput}
                                    placeholder={sessionData?.requestedAction === 'ANSWER_TEXT' ? "질문에 대한 답변을 입력하세요..." : "메시지를 입력하세요..."}
                                    placeholderTextColor="#64748b"
                                    value={userInput}
                                    onChangeText={setUserInput}
                                    onFocus={() => setKeyboardVisible(true)}
                                    // onBlur is removed to prevent flickering if user taps outside
                                    onSubmitEditing={handleSend}
                                    blurOnSubmit={false}
                                    returnKeyType="send"
                                />
                                <TouchableOpacity
                                    onPress={handleSend}
                                    style={[styles.sendButton, userInput.trim() ? styles.sendButtonActive : styles.sendButtonInactive]}
                                    disabled={!userInput.trim()}
                                >
                                    <MaterialIcons name="arrow-upward" size={22} color="white" />
                                </TouchableOpacity>
                            </View>
                        </View>
                    </View>
                </View>
            </KeyboardAvoidingView>

            {/* Bottom Nav - Hidden when keyboard is open */}
            {!isKeyboardVisible && (
                <SimpleBottomNav onNavigate={onNavigate} />
            )}
            {insets.bottom > 0 && (
                <View
                    style={{
                        position: 'absolute',
                        bottom: 0,
                        left: 0,
                        right: 0,
                        height: insets.bottom,
                        backgroundColor: '#111827',
                    }}
                />
            )}
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#111827', // bg-background-dark
    },
    chatContainer: {
        flex: 1,
    },
    scrollView: {
        flex: 1,
        paddingHorizontal: 24, // px-6
    },
    scrollContent: {
        paddingTop: 16,
        paddingBottom: 20
    },
    // Header
    headerContainer: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingHorizontal: 24,
        paddingVertical: 16,
        paddingBottom: 8,
        backgroundColor: 'transparent',
    },
    headerTitle: {
        fontSize: 24,
        fontWeight: 'bold',
        color: 'white',
        letterSpacing: -0.5,
    },
    headerStatus: {
        fontSize: 12,
        marginTop: 4,
        fontWeight: '500',
    },
    headerIcons: {
        flexDirection: 'row',
        gap: 16,
    },
    iconButton: {
        width: 40,
        height: 40,
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: 20,
        backgroundColor: '#1b2127',
        borderWidth: 1,
        borderColor: 'rgba(255,255,255,0.1)',
    },
    iconText: {
        color: 'white',
        fontSize: 12,
    },
    // Msg
    messageWrapper: {
        marginBottom: 24, // mb-6
        maxWidth: '85%',
    },
    messageUser: {
        alignSelf: 'flex-end',
    },
    messageAi: {
        alignSelf: 'flex-start',
    },
    messageBubble: {
        padding: 16,
        borderRadius: 16,
    },
    bubbleUser: {
        backgroundColor: '#3b82f6', // primary
        borderTopRightRadius: 0,
    },
    bubbleAi: {
        backgroundColor: '#1e293b', // surface-card
        borderWidth: 1,
        borderColor: 'rgba(255,255,255,0.1)',
        borderTopLeftRadius: 0,
    },
    messageText: {
        color: 'white',
        fontSize: 15,
        lineHeight: 24,
    },
    messageMeta: {
        color: '#94a3b8', // text-dim
        fontSize: 10,
        marginTop: 6,
        paddingHorizontal: 4,
        fontWeight: '500',
        fontStyle: 'italic',
    },
    // Loading
    loadingBubble: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 12,
    },
    loadingTextWrapper: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    loadingText: {
        color: '#94a3b8',
        fontSize: 15,
        fontWeight: '500',
    },
    dotContainer: {
        flexDirection: 'row',
        marginLeft: 4,
    },
    dot: {
        color: '#9cabba',
        fontSize: 15,
        fontWeight: 'bold',
    },
    // Input
    inputArea: {
        paddingHorizontal: 24,
        paddingVertical: 16,
        backgroundColor: '#111827',
        borderTopWidth: 1,
        borderTopColor: 'rgba(255,255,255,0.05)',
        minHeight: 80,
    },
    actionButtonsContainer: {
        flexDirection: 'row',
        justifyContent: 'center',
        gap: 12,
        marginBottom: 16,
        paddingHorizontal: 24,
    },
    actionButton: {
        paddingHorizontal: 16,
        paddingVertical: 10,
        borderRadius: 9999,
        flexDirection: 'row',
        alignItems: 'center',
        gap: 8,
        borderWidth: 1,
    },
    actionButtonPrimary: {
        backgroundColor: 'rgba(59,130,246,0.2)', // primary/20
        borderColor: '#3b82f6',
    },
    actionButtonSecondary: {
        backgroundColor: 'rgba(168,85,247,0.2)', // secondary/20
        borderColor: '#a855f7',
    },
    actionButtonTextPrimary: {
        color: '#3b82f6',
        fontWeight: 'bold',
        fontSize: 14,
    },
    actionButtonTextSecondary: {
        color: '#a855f7',
        fontWeight: 'bold',
        fontSize: 14,
    },
    menuArea: {
        flexDirection: 'row',
        justifyContent: 'space-around',
        marginBottom: 16,
        backgroundColor: '#1e293b',
        padding: 16,
        borderRadius: 12,
        borderWidth: 1,
        borderColor: 'rgba(255,255,255,0.1)',
        marginHorizontal: 4,
    },
    menuItem: {
        alignItems: 'center',
        gap: 8,
    },
    menuIconCircle: {
        width: 48,
        height: 48,
        borderRadius: 24,
        alignItems: 'center',
        justifyContent: 'center',
        borderWidth: 1,
    },
    menuIconBlue: { backgroundColor: 'rgba(59,130,246,0.2)', borderColor: 'rgba(59,130,246,0.3)' },
    menuIconPurple: { backgroundColor: 'rgba(168,85,247,0.2)', borderColor: 'rgba(168,85,247,0.3)' },
    menuIconEmerald: { backgroundColor: 'rgba(16,185,129,0.2)', borderColor: 'rgba(16,185,129,0.3)' },
    menuText: {
        color: '#cbd5e1', // slate-300
        fontSize: 12,
        fontWeight: '500',
    },
    inputRow: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 12,
    },
    plusButton: {
        width: 40,
        height: 40,
        borderRadius: 20,
        alignItems: 'center',
        justifyContent: 'center',
    },
    plusButtonActive: {
        backgroundColor: 'rgba(255,255,255,0.2)',
        transform: [{ rotate: '45deg' }]
    },
    plusButtonInactive: {
        backgroundColor: '#334155', // surface-light
    },
    inputWrapper: {
        flex: 1,
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: '#1e293b',
        borderRadius: 9999,
        paddingHorizontal: 16,
        paddingVertical: 4,
        borderWidth: 1,
        borderColor: 'rgba(255,255,255,0.1)',
        elevation: 5,
    },
    textInput: {
        flex: 1,
        color: 'white',
        paddingVertical: 12,
        fontSize: 15,
    },
    sendButton: {
        width: 40,
        height: 40,
        borderRadius: 20,
        alignItems: 'center',
        justifyContent: 'center',
    },
    sendButtonActive: {
        backgroundColor: '#3b82f6', // primary
    },
    sendButtonInactive: {
        backgroundColor: '#334155', // surface-highlight
    },
    // SimpleBottomNav
    navContainer: {
        backgroundColor: 'rgba(30, 41, 59, 0.95)', // surface-dark/95
        borderTopWidth: 1,
        borderTopColor: 'rgba(255,255,255,0.1)',
    },
    navContent: {
        flexDirection: 'row',
        justifyContent: 'space-around',
        alignItems: 'center',
        height: 64,
        paddingHorizontal: 8,
    },
    navItem: {
        flex: 1,
        alignItems: 'center',
        justifyContent: 'center',
        gap: 4,
        height: '100%',
    },
    navLabel: {
        fontSize: 10,
        fontWeight: '500',
    },
    navLabelActive: {
        color: '#3b82f6', // primary
        fontWeight: 'bold',
    },
    navLabelInactive: {
        color: '#6b7280', // gray-500
    },
    navIndicator: {
        position: 'absolute',
        bottom: 4,
        width: 4,
        height: 4,
        borderRadius: 2,
        backgroundColor: '#3b82f6',
    },
    // Media Preview Styles
    mediaPreview: {
        width: 200,
        height: 150,
        borderRadius: 12,
        marginBottom: 8,
        backgroundColor: '#1a2430',
    },
    audioPreview: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: 'rgba(13, 127, 242, 0.1)',
        paddingHorizontal: 12,
        paddingVertical: 8,
        borderRadius: 8,
        marginBottom: 8,
        gap: 8,
    },
    audioFileName: {
        color: '#0d7ff2',
        fontSize: 13,
        fontWeight: '500',
    },
    pendingIndicator: {
        fontSize: 11,
        color: '#94a3b8',
        fontStyle: 'italic',
        marginTop: 4,
    }
});
