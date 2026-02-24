import React, { useState, useRef, useEffect } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Image, ActivityIndicator, Dimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons } from '@expo/vector-icons';
import { CameraView, CameraType, useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import { useAlertStore } from '../store/useAlertStore';
import ocrApi from '../api/ocrApi';

const { width } = Dimensions.get('window');

export default function ReceiptScan({ navigation, route }: { navigation?: any; route?: any }) {
    const insets = useSafeAreaInsets();
    const [permission, requestPermission] = useCameraPermissions();
    const [facing, setFacing] = useState<CameraType>('back');
    const [enableTorch, setEnableTorch] = useState(false);
    const cameraRef = useRef<CameraView>(null);
    const [capturedImage, setCapturedImage] = useState<string | null>(null);
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [isCapturing, setIsCapturing] = useState(false);

    const vehicleId = route?.params?.vehicleId;

    const toggleFlash = () => {
        setEnableTorch((current) => !current);
    };

    const takePicture = async () => {
        if (isCapturing) return;
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

    const pickImage = async () => {
        const result = await ImagePicker.launchImageLibraryAsync({
            mediaTypes: ['images'],
            allowsEditing: false,
            quality: 0.8,
        });

        if (!result.canceled && result.assets && result.assets.length > 0) {
            setCapturedImage(result.assets[0].uri);
            setEnableTorch(false);
        }
    };

    const analyzeReceipt = async () => {
        if (!capturedImage) return;
        if (!vehicleId) {
            useAlertStore.getState().showAlert('오류', '차량 정보가 없습니다.', 'ERROR');
            return;
        }

        setIsAnalyzing(true);
        try {
            // Create FormData
            const formData = new FormData();
            formData.append('file', {
                uri: capturedImage,
                type: 'image/jpeg',
                name: 'receipt.jpg',
            } as any);

            // Call OCR analyze API (분석만)
            const result = await ocrApi.analyzeReceipt(formData);

            if (result?.ocrText === '텍스트 추출 실패' || !result?.ocrText?.trim()) {
                useAlertStore.getState().showAlert(
                    '영수증 인식 실패',
                    '영수증을 인식하지 못했습니다. 사진을 다시 찍어주세요.',
                    'WARNING'
                );
                return;
            }

            navigation.navigate('ReceiptResult', {
                vehicleId,
                imageUri: capturedImage,
                ocrResult: result,
                initialType: route?.params?.initialType,
            });
        } catch (error: any) {
            console.error('OCR Analysis Error:', error);
            useAlertStore.getState().showAlert(
                '분석 실패',
                error.message || '영수증 분석 중 오류가 발생했습니다.',
                'ERROR'
            );
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
                    <Text style={styles.titleText}>영수증 스캔</Text>
                </View>

                <View style={styles.iconButton} />
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
                                {/* Receipt Guide */}
                                <View style={styles.guideOverlay}>
                                    <View style={styles.receiptGuide}>
                                        <View style={[styles.cornerGuide, { top: 0, left: 0, borderTopWidth: 3, borderLeftWidth: 3, borderTopLeftRadius: 12 }]} />
                                        <View style={[styles.cornerGuide, { top: 0, right: 0, borderTopWidth: 3, borderRightWidth: 3, borderTopRightRadius: 12 }]} />
                                        <View style={[styles.cornerGuide, { bottom: 0, left: 0, borderBottomWidth: 3, borderLeftWidth: 3, borderBottomLeftRadius: 12 }]} />
                                        <View style={[styles.cornerGuide, { bottom: 0, right: 0, borderBottomWidth: 3, borderRightWidth: 3, borderBottomRightRadius: 12 }]} />
                                    </View>
                                </View>

                                <View style={styles.guideTextContainer}>
                                    <View style={styles.guideTextBox}>
                                        <Text style={styles.guideTitle}>영수증을 가이드라인에 맞춰주세요</Text>
                                        <Text style={styles.guideSubtitle}>텍스트가 잘 보이도록 촬영해주세요</Text>
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
                            <Image source={{ uri: capturedImage }} style={StyleSheet.absoluteFill} resizeMode="contain" />
                            <View style={styles.overlay} />

                            {isAnalyzing && (
                                <View style={styles.loadingOverlay}>
                                    <ActivityIndicator size="large" color="#0d7ff2" />
                                    <Text style={styles.loadingText}>영수증 분석 중...</Text>
                                </View>
                            )}
                        </View>
                    </View>
                )}
            </View>

            {/* Bottom Controls */}
            <View style={[styles.bottomControls, { paddingBottom: insets.bottom + 20 }]}>
                {capturedImage ? (
                    <View style={styles.previewControls}>
                        <TouchableOpacity
                            onPress={retakePicture}
                            style={styles.retakeButton}
                            disabled={isAnalyzing}
                        >
                            <Text style={styles.retakeText}>재촬영</Text>
                        </TouchableOpacity>

                        <TouchableOpacity
                            onPress={analyzeReceipt}
                            style={styles.analyzeButton}
                            disabled={isAnalyzing}
                        >
                            {isAnalyzing ? (
                                <ActivityIndicator color="white" size="small" />
                            ) : (
                                <>
                                    <MaterialIcons name="search" size={20} color="white" />
                                    <Text style={styles.analyzeText}>분석하기</Text>
                                </>
                            )}
                        </TouchableOpacity>
                    </View>
                ) : (
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
                            onPress={pickImage}
                            disabled={isCapturing}
                        >
                            <View style={[styles.controlIcon, { backgroundColor: '#1e2936' }]}>
                                <MaterialIcons name="photo-library" size={22} color="white" />
                            </View>
                            <Text style={[styles.controlText, { color: '#94a3b8' }]}>갤러리</Text>
                        </TouchableOpacity>
                    </View>
                )}
            </View>
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
        fontSize: 14,
    },
    guideOverlay: {
        position: 'absolute',
        top: 120,
        left: 24,
        right: 24,
        bottom: 200,
        alignItems: 'center',
        justifyContent: 'center',
    },
    receiptGuide: {
        width: '100%',
        height: '100%',
        maxWidth: 320,
        maxHeight: 450,
        position: 'relative',
    },
    cornerGuide: {
        position: 'absolute',
        width: 40,
        height: 40,
        borderColor: '#0d7ff2',
    },
    guideTextContainer: {
        position: 'absolute',
        bottom: 180,
        width: '100%',
        paddingHorizontal: 24,
        alignItems: 'center',
    },
    guideTextBox: {
        backgroundColor: 'rgba(0,0,0,0.7)',
        paddingHorizontal: 24,
        paddingVertical: 16,
        borderRadius: 16,
        borderWidth: 1,
        borderColor: 'rgba(255,255,255,0.2)',
        alignItems: 'center',
    },
    guideTitle: {
        color: 'white',
        fontWeight: 'bold',
        fontSize: 16,
        marginBottom: 4,
    },
    guideSubtitle: {
        color: '#cbd5e1',
        fontSize: 12,
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
    },
    previewControls: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingHorizontal: 32,
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
        paddingHorizontal: 48,
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
    },
    shutterButtonContainer: {
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
    overlay: {
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0,0,0,0.1)',
    },
    loadingOverlay: {
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(0,0,0,0.6)',
    },
    loadingText: {
        color: 'white',
        marginTop: 16,
        fontWeight: 'bold',
    },
});
