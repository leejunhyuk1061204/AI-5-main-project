import React, { useEffect, useState, useRef } from 'react';
import { View, Text, TouchableOpacity, Dimensions, StyleSheet, Image, ActivityIndicator, StatusBar as RNStatusBar } from 'react-native';
import { useAlertStore } from '../store/useAlertStore';
import { diagnoseImage, replyToDiagnosisSession } from '../api/aiApi';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons } from '@expo/vector-icons';
import { CameraView, CameraType, useCameraPermissions } from 'expo-camera';

const { width } = Dimensions.get('window');

// Main Camera Component
export default function Filming({ navigation, route }: { navigation?: any; route?: any }) {
    const insets = useSafeAreaInsets();
    const [permission, requestPermission] = useCameraPermissions();
    const [facing, setFacing] = useState<CameraType>('back');
    const [enableTorch, setEnableTorch] = useState(false);
    const cameraRef = useRef<CameraView>(null);
    const [capturedImage, setCapturedImage] = useState<string | null>(null);
    const [isAnalyzing, setIsAnalyzing] = useState(false);

    // New: Capture loading state to prevent double taps and show feedback
    const [isCapturing, setIsCapturing] = useState(false);

    const toggleCameraFacing = () => {
        setFacing((current) => (current === 'back' ? 'front' : 'back'));
    };

    const toggleFlash = () => {
        setEnableTorch((current) => !current);
    };

    const takePicture = async () => {
        if (isCapturing) return; // Prevent double taps
        if (!cameraRef.current) return;

        setIsCapturing(true);
        try {
            const photo = await cameraRef.current.takePictureAsync({
                quality: 0.8,
                skipProcessing: true,
            });
            if (photo?.uri) {
                setCapturedImage(photo.uri);
                setEnableTorch(false);
            }
        } catch (error) {
            console.error('Failed to take picture:', error);
            useAlertStore.getState().showAlert('오류', '사진 촬영 중 문제가 발생했습니다.', 'ERROR');
        } finally {
            setIsCapturing(false);
        }
    };

    const retakePicture = () => {
        setCapturedImage(null);
    };

    const analyzeImage = async () => {
        if (!capturedImage) return;
        const sessionId = route?.params?.sessionId;

        setIsAnalyzing(true);
        try {
            let result;
            if (sessionId) {
                // If we are in an interactive session, use REPLY endpoint
                result = await replyToDiagnosisSession(sessionId, {
                    userResponse: "사진을 촬영했습니다.", // Default text for media reply 
                    vehicleId: route?.params?.vehicleId || '00000000-0000-0000-0000-000000000000'
                }, capturedImage);
            } else {
                // Otherwise start a new diagnosis
                result = await diagnoseImage(capturedImage);
            }

            if (!navigation) {
                useAlertStore.getState().showAlert('진단 완료', '진단 결과가 준비되었습니다.', 'SUCCESS');
                return;
            }

            if (route?.params?.from === 'chatbot') {
                navigation.navigate('AiCompositeDiag', { diagnosisResult: result });
            } else if (route?.params?.from === 'professional') {
                navigation.navigate('AiProfessionalDiag', { diagnosisResult: result });
            } else {
                navigation.navigate('VisualDiagnosis', { diagnosisResult: result, capturedImage: capturedImage });
            }

        } catch (error: any) {
            console.error('Diagnosis Error:', error);
            useAlertStore.getState().showAlert('진단 실패', error.message || '서버 통신 중 오류가 발생했습니다.', 'ERROR');
        } finally {
            setIsAnalyzing(false);
        }
    };

    useEffect(() => {
        if (!permission) {
            requestPermission();
        }
    }, [permission]);

    if (!permission) return <View style={styles.loadingContainer} />;

    if (!permission.granted) {
        return (
            <View style={styles.permissionContainer}>
                <Text style={styles.permissionText}>카메라 권한이 필요합니다.</Text>
                <TouchableOpacity onPress={requestPermission} style={styles.permissionButton}>
                    <Text style={styles.permissionButtonText}>권한 허용</Text>
                </TouchableOpacity>
            </View>
        );
    }

    return (
        <View style={styles.container}>
            <StatusBar style="light" />

            {/* Top Bar */}
            <View style={[styles.topBar, { paddingTop: insets.top + 10 }]}>
                <TouchableOpacity
                    onPress={() => navigation?.goBack?.()}
                    style={styles.iconButton}
                >
                    <MaterialIcons name="close" size={24} color="white" />
                </TouchableOpacity>

                <View style={styles.titleContainer}>
                    <Text style={styles.titleText}>AI VISUAL SCAN</Text>
                </View>

                <TouchableOpacity style={styles.iconButton}>
                    <MaterialIcons name="help-outline" size={24} color="white" />
                </TouchableOpacity>
            </View>

            {/* Content Area */}
            <View style={StyleSheet.absoluteFill}>
                {/* Camera View */}
                <View style={[StyleSheet.absoluteFill, { opacity: capturedImage ? 0 : 1, zIndex: capturedImage ? 0 : 1 }]}>
                    <CameraView
                        ref={cameraRef}
                        style={StyleSheet.absoluteFill}
                        facing={facing}
                        enableTorch={enableTorch}
                    >
                        {!capturedImage && (
                            <>
                                {/* Guidelines */}
                                <View style={[styles.cornerGuide, { top: 128, left: 32, borderTopWidth: 3, borderLeftWidth: 3, borderTopLeftRadius: 12 }]} />
                                <View style={[styles.cornerGuide, { top: 128, right: 32, borderTopWidth: 3, borderRightWidth: 3, borderTopRightRadius: 12 }]} />
                                <View style={[styles.cornerGuide, { bottom: 192, left: 32, borderBottomWidth: 3, borderLeftWidth: 3, borderBottomLeftRadius: 12 }]} />
                                <View style={[styles.cornerGuide, { bottom: 192, right: 32, borderBottomWidth: 3, borderRightWidth: 3, borderBottomRightRadius: 12 }]} />

                                <View style={styles.centerGuideContainer} pointerEvents="none">
                                    <View style={styles.centerCircle}>
                                        <View style={styles.innerCircle} />
                                        <View style={styles.scanLabel}>
                                            <MaterialIcons name="build" size={14} color="#0d7ff2" />
                                            <Text style={styles.scanText}>SCAN</Text>
                                        </View>
                                    </View>
                                </View>

                                <View style={styles.guideTextContainer} pointerEvents="none">
                                    <View style={styles.guideTextBox}>
                                        <Text style={styles.guideTitle}>가이드라인에 맞춰 부품을 촬영해 주세요</Text>
                                        <Text style={styles.guideSubtitle}>어두운 곳에서는 플래시를 켜주세요</Text>
                                    </View>
                                </View>
                            </>
                        )}
                    </CameraView>
                </View>

                {/* Preview Image */}
                {capturedImage && (
                    <View style={[StyleSheet.absoluteFill, { zIndex: 10 }]}>
                        <View style={{ flex: 1, position: 'relative' }}>
                            <Image source={{ uri: capturedImage }} style={StyleSheet.absoluteFill} resizeMode="cover" />
                            <View style={styles.overlay} />

                            {isAnalyzing && (
                                <View style={styles.loadingOverlay}>
                                    <ActivityIndicator size="large" color="#0d7ff2" />
                                    <Text style={styles.loadingText}>AI 분석 중...</Text>
                                </View>
                            )}
                        </View>
                    </View>
                )}
            </View>

            {/* Bottom Controls */}
            <View style={[styles.bottomControls, { paddingBottom: insets.bottom + 20 }]}>
                {capturedImage ? (
                    // Preview Controls
                    <View style={styles.previewControls}>
                        <TouchableOpacity
                            onPress={retakePicture}
                            style={styles.retakeButton}
                            disabled={isAnalyzing}
                        >
                            <Text style={styles.retakeText}>재촬영</Text>
                        </TouchableOpacity>

                        <TouchableOpacity
                            onPress={analyzeImage}
                            style={styles.analyzeButton}
                            disabled={isAnalyzing}
                        >
                            {isAnalyzing ? (
                                <ActivityIndicator color="white" size="small" />
                            ) : (
                                <>
                                    <MaterialIcons name="check" size={20} color="white" />
                                    <Text style={styles.analyzeText}>진단 시작</Text>
                                </>
                            )}
                        </TouchableOpacity>
                    </View>
                ) : (
                    // Camera Controls
                    <View style={styles.cameraControls}>
                        <TouchableOpacity
                            style={styles.controlButton}
                            onPress={toggleFlash}
                            disabled={isCapturing}
                        >
                            <View style={[styles.controlIcon, { backgroundColor: enableTorch ? 'rgba(234,179,8,0.2)' : '#1e2936', borderColor: enableTorch ? 'rgba(234,179,8,0.5)' : 'rgba(255,255,255,0.1)' }]}>
                                <MaterialIcons name={enableTorch ? "flash-on" : "flash-off"} size={22} color={enableTorch ? "#fbbf24" : "white"} />
                            </View>
                            <Text style={[styles.controlText, { color: enableTorch ? '#eab308' : '#94a3b8' }]}>플래시</Text>
                        </TouchableOpacity>

                        <TouchableOpacity
                            style={[styles.shutterButtonContainer, isCapturing && { opacity: 0.8 }]}
                            onPress={takePicture}
                            disabled={isCapturing}
                        >
                            <View style={styles.shutterButtonOuter}>
                                {isCapturing ? (
                                    <ActivityIndicator color="#0d7ff2" size="small" />
                                ) : (
                                    <View style={styles.shutterButtonInner} />
                                )}
                            </View>
                        </TouchableOpacity>

                        <TouchableOpacity
                            style={styles.controlButton}
                            onPress={toggleCameraFacing}
                            disabled={isCapturing}
                        >
                            <View style={[styles.controlIcon, { backgroundColor: '#1e2936' }]}>
                                <MaterialIcons name="flip-camera-ios" size={22} color="white" />
                            </View>
                            <Text style={[styles.controlText, { color: '#94a3b8' }]}>전환</Text>
                        </TouchableOpacity>
                    </View>
                )}
            </View>
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: 'black',
    },
    loadingContainer: {
        flex: 1,
        backgroundColor: '#050F1A',
    },
    permissionContainer: {
        flex: 1,
        backgroundColor: '#050F1A',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
    },
    permissionText: {
        color: 'white',
        textAlign: 'center',
        marginBottom: 16,
    },
    permissionButton: {
        backgroundColor: '#0d7ff2',
        paddingHorizontal: 16,
        paddingVertical: 8,
        borderRadius: 8,
    },
    permissionButtonText: {
        color: 'white',
        fontWeight: 'bold',
    },
    topBar: {
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 20,
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingHorizontal: 24,
    },
    iconButton: {
        width: 40,
        height: 40,
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: 20,
        backgroundColor: 'rgba(0,0,0,0.2)',
    },
    titleContainer: {
        backgroundColor: 'rgba(0,0,0,0.4)',
        paddingHorizontal: 16,
        paddingVertical: 6,
        borderRadius: 999,
        borderWidth: 1,
        borderColor: 'rgba(255,255,255,0.1)',
    },
    titleText: {
        color: 'white',
        fontWeight: 'bold',
        fontSize: 12,
        letterSpacing: 1,
    },
    bottomControls: {
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        backgroundColor: '#101922',
        borderTopRightRadius: 32,
        borderTopLeftRadius: 32,
        borderTopWidth: 1,
        borderColor: 'rgba(255,255,255,0.1)',
        zIndex: 20,
        paddingTop: 32,
        shadowColor: 'black',
        shadowOpacity: 0.5,
        shadowRadius: 20,
        elevation: 10,
    },
    previewControls: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingHorizontal: 32,
        width: '100%',
        maxWidth: 450,
        alignSelf: 'center',
    },
    retakeButton: {
        flex: 1,
        backgroundColor: '#1e2936',
        paddingVertical: 16,
        borderRadius: 12,
        alignItems: 'center',
        marginRight: 12,
    },
    retakeText: {
        color: '#cbd5e1',
        fontWeight: 'bold',
    },
    analyzeButton: {
        flex: 2,
        backgroundColor: '#0d7ff2',
        paddingVertical: 16,
        borderRadius: 12,
        alignItems: 'center',
        flexDirection: 'row',
        justifyContent: 'center',
        gap: 8,
    },
    analyzeText: {
        color: 'white',
        fontWeight: 'bold',
        fontSize: 18,
    },
    cameraControls: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        maxWidth: 380,
        width: '100%',
        alignSelf: 'center',
        paddingHorizontal: 32,
    },
    controlButton: {
        alignItems: 'center',
        gap: 8,
    },
    controlIcon: {
        width: 48,
        height: 48,
        borderRadius: 24,
        borderWidth: 1,
        borderColor: 'rgba(255,255,255,0.1)',
        alignItems: 'center',
        justifyContent: 'center',
    },
    controlText: {
        fontSize: 11,
        fontWeight: '500',
        letterSpacing: 0.5,
    },
    shutterButtonContainer: {
        position: 'relative',
        alignItems: 'center',
        justifyContent: 'center',
        marginTop: -16,
    },
    shutterButtonOuter: {
        width: 80,
        height: 80,
        borderRadius: 999,
        borderWidth: 3,
        borderColor: 'rgba(255,255,255,0.2)',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#101922',
    },
    shutterButtonInner: {
        width: 64,
        height: 64,
        borderRadius: 999,
        backgroundColor: '#0d7ff2',
        borderWidth: 3,
        borderColor: '#1e2936',
    },
    cornerGuide: {
        position: 'absolute',
        width: 40,
        height: 40,
        borderColor: '#0d7ff2',
    },
    centerGuideContainer: {
        position: 'absolute',
        inset: 0,
        alignItems: 'center',
        justifyContent: 'center',
        paddingBottom: 40,
    },
    centerCircle: {
        width: '85%',
        aspectRatio: 1,
        maxWidth: 340,
        borderRadius: 999,
        borderWidth: 2,
        borderStyle: 'dashed',
        borderColor: '#0d7ff2',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(13,127,242,0.05)',
    },
    innerCircle: {
        width: '45%',
        aspectRatio: 1,
        borderRadius: 999,
        borderWidth: 1,
        borderColor: 'rgba(13,127,242,0.5)',
    },
    scanLabel: {
        position: 'absolute',
        top: -12,
        backgroundColor: 'rgba(13,127,242,0.2)',
        borderWidth: 1,
        borderColor: '#0d7ff2',
        paddingHorizontal: 16,
        paddingVertical: 6,
        borderRadius: 999,
        flexDirection: 'row',
        alignItems: 'center',
        gap: 6,
    },
    scanText: {
        color: '#0d7ff2',
        fontSize: 12,
        fontWeight: 'bold',
        letterSpacing: 2,
    },
    guideTextContainer: {
        position: 'absolute',
        bottom: 176,
        width: '100%',
        paddingHorizontal: 24,
        alignItems: 'center',
        justifyContent: 'center',
    },
    guideTextBox: {
        backgroundColor: 'rgba(0,0,0,0.7)',
        paddingHorizontal: 24,
        paddingVertical: 16,
        borderRadius: 16,
        borderWidth: 1,
        borderColor: 'rgba(255,255,255,0.2)',
        width: '100%',
        maxWidth: 380,
        alignItems: 'center',
    },
    guideTitle: {
        color: 'white',
        fontWeight: 'bold',
        fontSize: 16,
        marginBottom: 4,
        textAlign: 'center',
    },
    guideSubtitle: {
        color: '#cbd5e1',
        fontSize: 12,
        textAlign: 'center',
    },
    overlay: {
        position: 'absolute',
        inset: 0,
        backgroundColor: 'rgba(0,0,0,0.2)',
    },
    loadingOverlay: {
        position: 'absolute',
        inset: 0,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(0,0,0,0.6)',
        zIndex: 50,
    },
    loadingText: {
        color: 'white',
        marginTop: 16,
        fontWeight: 'bold',
        letterSpacing: 2,
    },
});
