import React, { useState, useEffect, useRef } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator, Animated } from 'react-native';
import { Audio } from 'expo-av';
import { MaterialIcons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { useNavigation, useRoute } from '@react-navigation/native';
import { useAiDiagnosisStore } from '../store/useAiDiagnosisStore';
import { useAlertStore } from '../store/useAlertStore';
import { replyToDiagnosisSession, diagnoseEngineSound } from '../api/aiApi';
import * as DocumentPicker from 'expo-document-picker';

// Animation Component for Recording Text
const RecordingText = () => {
    const opacity = useRef(new Animated.Value(1)).current;

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
        <Animated.Text style={[styles.recordingText, { opacity }]}>
            녹음 중...
        </Animated.Text>
    );
};

export default function ChatAudioScreen() {
    const navigation = useNavigation<any>();
    const route = useRoute<any>();
    const insets = useSafeAreaInsets();

    // Params
    const { sessionId } = route.params || {};
    // Use param or fallback to store
    const vehicleId = route.params?.vehicleId || useAiDiagnosisStore(state => state.selectedVehicleId);

    // Audio State
    const [recording, setRecording] = useState<Audio.Recording | null>(null);
    const [recordedUri, setRecordedUri] = useState<string | null>(null);
    const [sound, setSound] = useState<Audio.Sound | null>(null);
    const [isPlaying, setIsPlaying] = useState(false);

    // Logic State
    const [isSending, setIsSending] = useState(false);

    // Stores
    const { setVehicleId, updateStatus } = useAiDiagnosisStore();

    // Visualizer Animations
    const animations = useRef([...Array(9)].map(() => new Animated.Value(1))).current;
    const barHeights = [32, 48, 64, 96, 56, 80, 40, 48, 24];

    useEffect(() => {
        return () => {
            // Cleanup
            if (recording) recording.stopAndUnloadAsync();
            if (sound) sound.unloadAsync();
        };
    }, []);

    // Animation Effect
    useEffect(() => {
        if (recording || isPlaying) {
            const loops = animations.map((anim, i) => {
                return Animated.loop(
                    Animated.sequence([
                        Animated.timing(anim, {
                            toValue: Math.random() * 0.5 + 0.5,
                            duration: 200 + Math.random() * 300,
                            useNativeDriver: true,
                        }),
                        Animated.timing(anim, {
                            toValue: 1.2,
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
                animations.forEach(anim => anim.setValue(1));
            };
        }
    }, [recording, isPlaying]);

    const startRecording = async () => {
        try {
            const perm = await Audio.requestPermissionsAsync();
            if (perm.status !== 'granted') return;

            await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
            const { recording: newRecording } = await Audio.Recording.createAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
            setRecording(newRecording);
        } catch (err) {
            console.error(err);
        }
    };

    const stopRecording = async () => {
        if (!recording) return;
        setRecording(null);
        await recording.stopAndUnloadAsync();
        const uri = recording.getURI();
        if (uri) setRecordedUri(uri);
    };

    const togglePlayback = async () => {
        if (!recordedUri) return;
        if (sound) {
            if (isPlaying) {
                await sound.pauseAsync();
                setIsPlaying(false);
            } else {
                await sound.playAsync();
                setIsPlaying(true);
            }
        } else {
            const { sound: newSound } = await Audio.Sound.createAsync({ uri: recordedUri });
            setSound(newSound);
            await newSound.playAsync();
            setIsPlaying(true);
            newSound.setOnPlaybackStatusUpdate(status => {
                if (status.isLoaded && status.didJustFinish) {
                    setIsPlaying(false);
                }
            });
        }
    };

    const pickAudioFile = async () => {
        try {
            const result = await DocumentPicker.getDocumentAsync({
                type: 'audio/*',
                copyToCacheDirectory: true,
            });

            if (!result.canceled && result.assets && result.assets.length > 0) {
                setRecordedUri(result.assets[0].uri);
            }
        } catch (err) {
            console.error(err);
        }
    };

    const handleSend = async () => {
        if (!recordedUri) return;
        if (!vehicleId) {
            useAlertStore.getState().showAlert('오류', '차량 ID가 없습니다.', 'ERROR');
            return;
        }

        setIsSending(true);
        try {
            // 1. 즉시 채팅방에 표시될 임시 메시지 정보 전달
            const pendingMessage = {
                type: 'audio',
                uri: recordedUri,
                text: '엔진 소리를 녹음했습니다.',
                timestamp: Date.now()
            };

            // 2. Send API Request
            if (sessionId) {
                await replyToDiagnosisSession(sessionId, {
                    userResponse: "엔진 소리를 녹음했습니다.",
                    vehicleId: vehicleId
                }, undefined, recordedUri);
            } else {
                const result = await diagnoseEngineSound(recordedUri, vehicleId);
                if (result?.sessionId) {
                    useAiDiagnosisStore.setState({ currentSessionId: result.sessionId });
                    setVehicleId(vehicleId);
                    updateStatus(result.sessionId);
                }
            }

            // 3. Go Back with Pending Message Info
            navigation.navigate('AiDiagChat', {
                sessionId,
                vehicleId,
                pendingMessage
            });

        } catch (error) {
            console.error(error);
            useAlertStore.getState().showAlert('전송 실패', '오디오 전송 중 오류가 발생했습니다.', 'ERROR');
            setIsSending(false);
            useAiDiagnosisStore.setState({ isWaitingForAi: false, status: 'IDLE' });
        }
    };

    const handleRetake = () => {
        setRecordedUri(null);
        if (sound) {
            sound.unloadAsync();
            setSound(null);
        }
        setIsPlaying(false);
    };

    return (
        <View style={styles.container}>
            <StatusBar style="light" />

            {/* Header */}
            <View style={[styles.header, { marginTop: insets.top }]}>
                <TouchableOpacity onPress={() => navigation.goBack()} style={styles.iconBtn}>
                    <MaterialIcons name="close" size={24} color="white" />
                </TouchableOpacity>
                <Text style={styles.headerTitle}>소리 녹음</Text>
                <View style={{ width: 40 }} />
            </View>

            {/* Main Content */}
            <View style={styles.content}>
                <View style={styles.messageContainer}>
                    <Text style={styles.mainTitle}>
                        {recordedUri ? "녹음된 소리를 확인해 주세요" : (recording ? "소리를 녹음 중입니다..." : "엔진 시동을 걸고\n소리를 녹음해 주세요")}
                    </Text>
                    <Text style={styles.subTitle}>
                        {recordedUri ? "재생 버튼을 눌러 소리를 확인할 수 있습니다." : "정확한 분석을 위해 주변 소음을\n최소화해 주시기 바랍니다."}
                    </Text>
                </View>

                {/* Visualizer */}
                <View style={styles.visualizerContainer}>
                    <View style={styles.visualizerBars}>
                        {animations.map((anim, index) => (
                            <Animated.View
                                key={index}
                                style={{
                                    width: 6,
                                    height: barHeights[index],
                                    backgroundColor: (isPlaying || recording) ? '#a855f7' : '#0d7ff2',
                                    borderRadius: 9999,
                                    transform: [{ scaleY: anim }],
                                    marginHorizontal: 3,
                                    opacity: 0.8
                                }}
                            />
                        ))}
                    </View>
                </View>

                {/* Controls */}
                {!recordedUri ? (
                    // Recording State
                    <View style={styles.recordControls}>
                        <View style={styles.recordBtnWrapper}>
                            <TouchableOpacity
                                onPress={recording ? stopRecording : startRecording}
                                style={[styles.recordBtn, recording ? styles.recordingActive : styles.recordingInactive]}
                            >
                                <MaterialIcons name={recording ? "stop" : "mic"} size={32} color="white" />
                            </TouchableOpacity>
                            {recording ? (
                                <RecordingText />
                            ) : (
                                <Text style={styles.btnLabel}>녹음 시작</Text>
                            )}
                        </View>

                        {!recording && (
                            <View style={styles.recordBtnWrapper}>
                                <TouchableOpacity onPress={pickAudioFile} style={styles.fileBtn}>
                                    <MaterialIcons name="file-present" size={32} color="white" />
                                </TouchableOpacity>
                                <Text style={styles.btnLabel}>파일 선택</Text>
                            </View>
                        )}
                    </View>
                ) : (
                    // Review State
                    <View style={styles.reviewControls}>
                        <TouchableOpacity
                            onPress={togglePlayback}
                            style={styles.playBtn}
                        >
                            <MaterialIcons name={isPlaying ? "pause" : "play-arrow"} size={48} color="white" style={{ marginLeft: isPlaying ? 0 : 4 }} />
                        </TouchableOpacity>

                        <View style={styles.actionRowWrapper}>
                            <View style={styles.actionRow}>
                                <TouchableOpacity onPress={handleRetake} style={styles.retakeButton} disabled={isSending}>
                                    <Text style={styles.retakeText}>재녹음</Text>
                                </TouchableOpacity>
                                <TouchableOpacity onPress={handleSend} style={styles.sendButton} disabled={isSending}>
                                    {isSending ? <ActivityIndicator color="white" /> : <Text style={styles.sendText}>전송하기</Text>}
                                </TouchableOpacity>
                            </View>
                        </View>
                    </View>
                )}
            </View>
        </View>
    );
}

const styles = StyleSheet.create({
    container: { flex: 1, backgroundColor: '#111827' }, // Using the dark engine sound bg
    header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16 },
    iconBtn: { padding: 8 },
    headerTitle: { color: 'white', fontSize: 18, fontWeight: 'bold' },

    content: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingBottom: 40 },
    messageContainer: { alignItems: 'center', marginBottom: 48 },
    mainTitle: { fontSize: 24, fontWeight: 'bold', color: 'white', textAlign: 'center', marginBottom: 12, lineHeight: 36 },
    subTitle: { fontSize: 14, color: '#94a3b8', textAlign: 'center', lineHeight: 20 },

    visualizerContainer: { height: 160, marginBottom: 48, alignItems: 'center', justifyContent: 'center' },
    visualizerBars: { flexDirection: 'row', alignItems: 'center', height: '100%' },

    recordControls: { flexDirection: 'row', gap: 32 },
    recordBtnWrapper: { alignItems: 'center', gap: 16 },
    recordBtn: { width: 80, height: 80, borderRadius: 40, alignItems: 'center', justifyContent: 'center', shadowColor: '#000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.3, shadowRadius: 4, elevation: 5 },
    recordingActive: { backgroundColor: '#ef4444' },
    recordingInactive: { backgroundColor: '#0d7ff2' },
    fileBtn: { width: 80, height: 80, borderRadius: 40, backgroundColor: '#1a2430', borderWidth: 1, borderColor: '#334155', alignItems: 'center', justifyContent: 'center' },
    btnLabel: { color: '#64748b', fontSize: 14, fontWeight: '500' },
    recordingText: { color: '#ef4444', fontSize: 14, fontWeight: 'bold' },

    reviewControls: { width: '100%', alignItems: 'center' },
    playBtn: { width: 96, height: 96, borderRadius: 48, backgroundColor: '#0d7ff2', alignItems: 'center', justifyContent: 'center', marginBottom: 40, shadowColor: '#3b82f6', shadowOpacity: 0.4, shadowRadius: 10, elevation: 10 },

    actionRowWrapper: { width: '100%', paddingHorizontal: 24, marginBottom: 16 },
    actionRow: { flexDirection: 'row', gap: 12, width: '100%' },
    retakeButton: { flex: 1, height: 56, backgroundColor: '#1e293b', borderRadius: 12, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: '#475569' },
    retakeText: { color: '#cbd5e1', fontSize: 16, fontWeight: 'bold' },
    sendButton: { flex: 1, height: 56, backgroundColor: '#0d7ff2', borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
    sendText: { color: 'white', fontSize: 16, fontWeight: 'bold' },
});
