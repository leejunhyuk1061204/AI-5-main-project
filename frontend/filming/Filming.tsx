import React, { useEffect, useState, useRef } from 'react';
import { View, Text, TouchableOpacity, Dimensions, StyleSheet, Image, ActivityIndicator, Alert } from 'react-native';
import { diagnoseImage } from '../api/aiApi';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import { CameraView, CameraType, useCameraPermissions } from 'expo-camera';
import { LinearGradient } from 'expo-linear-gradient';

const { width, height } = Dimensions.get('window');

export default function Filming() {
    const navigation = useNavigation<any>();
    const route = useRoute<any>();
    const insets = useSafeAreaInsets();
    const [permission, requestPermission] = useCameraPermissions();
    const [facing, setFacing] = useState<CameraType>('back');
    const [enableTorch, setEnableTorch] = useState(false);
    const cameraRef = useRef<CameraView>(null);
    const [capturedImage, setCapturedImage] = useState<string | null>(null);
    const [isAnalyzing, setIsAnalyzing] = useState(false);

    const toggleCameraFacing = () => {
        setFacing((current) => (current === 'back' ? 'front' : 'back'));
    };

    const toggleFlash = () => {
        setEnableTorch((current) => !current);
    };

    const takePicture = async () => {
        if (cameraRef.current) {
            try {
                const photo = await cameraRef.current.takePictureAsync({
                    quality: 0.8,
                    skipProcessing: true, // 안드로이드 속도 최적화
                });
                if (photo?.uri) {
                    setCapturedImage(photo.uri);
                    setEnableTorch(false); // 촬영 후 플래시 끄기
                }
            } catch (error) {
                console.error('Failed to take picture:', error);
                Alert.alert('오류', '사진 촬영 중 문제가 발생했습니다.');
            }
        }
    };

    const retakePicture = () => {
        setCapturedImage(null);
    };

    const analyzeImage = async () => {
        if (!capturedImage) return;

        setIsAnalyzing(true);
        try {
            // 여기에 API 호출 로직 추가
            // const result = await diagnoseImage(capturedImage);
            // navigation.navigate('VisualDiagnosis', { result });

            // 임시로 2초 후 성공 처리 (API 연동 전 테스트용)
            // await new Promise(resolve => setTimeout(resolve, 2000));
            // Alert.alert('진단 완료', 'AI 진단이 완료되었습니다. (API 연결 필요)');

            // 실제 API 호출 (주석 해제 후 사용)
            const result = await diagnoseImage(capturedImage);

            // Check if initiated from Chatbot (AiCompositeDiag)
            if (route.params?.from === 'chatbot') {
                navigation.navigate('AiCompositeDiag', { diagnosisResult: result });
            } else {
                navigation.navigate('VisualDiagnosis', { diagnosisResult: result, capturedImage: capturedImage });
            }

        } catch (error) {
            Alert.alert('진단 실패', '서버 통신 중 오류가 발생했습니다.');
        } finally {
            setIsAnalyzing(false);
        }
    };

    useEffect(() => {
        // Request camera permission on mount
        if (!permission) {
            requestPermission();
        }
    }, [permission]);

    if (!permission) {
        // Camera permissions are still loading
        return <View className="flex-1 bg-[#050F1A]" />;
    }

    if (!permission.granted) {
        // Camera permissions are not granted yet
        return (
            <View className="flex-1 bg-[#050F1A] items-center justify-center p-6">
                <Text className="text-white text-center mb-4">카메라 권한이 필요합니다.</Text>
                <TouchableOpacity onPress={requestPermission} className="bg-primary px-4 py-2 rounded-lg">
                    <Text className="text-white font-bold">권한 허용</Text>
                </TouchableOpacity>
            </View>
        );
    }

    return (
        <View className="flex-1 bg-black">
            <StatusBar style="light" />

            {/* Top Bar with safe area top margin */}
            <View
                className="flex-row items-start justify-between px-4 z-30 absolute top-0 left-0 right-0"
                style={{ paddingTop: insets.top + 10 }}
            >
                <TouchableOpacity
                    onPress={() => navigation.goBack()}
                    className="w-10 h-10 items-center justify-center rounded-full bg-black/20 active:bg-white/10 backdrop-blur-md"
                >
                    <MaterialIcons name="arrow-back-ios" size={20} color="white" style={{ marginLeft: 4 }} />
                </TouchableOpacity>

                <View className="items-center bg-black/20 px-4 py-1.5 rounded-full backdrop-blur-md">
                    <Text className="text-white text-base font-bold">AI 복합 진단</Text>
                </View>

                <TouchableOpacity className="w-10 h-10 items-center justify-center rounded-full bg-black/20 active:bg-white/10 backdrop-blur-md">
                    <MaterialIcons name="help-outline" size={24} color="white" />
                </TouchableOpacity>
            </View>

            {/* Main Content (Camera View or Preview) */}
            <View className="absolute inset-0 z-0 bg-black">
                {capturedImage ? (
                    <View className="flex-1 relative">
                        <Image source={{ uri: capturedImage }} style={StyleSheet.absoluteFill} resizeMode="cover" />
                        {/* Preview Overlay */}
                        <View className="absolute inset-0 bg-black/20" />

                        {isAnalyzing && (
                            <View className="absolute inset-0 items-center justify-center bg-black/60 z-50">
                                <ActivityIndicator size="large" color="#0d7ff2" />
                                <Text className="text-white mt-4 font-bold tracking-widest">AI 분석 중...</Text>
                            </View>
                        )}
                    </View>
                ) : (
                    <CameraView
                        ref={cameraRef}
                        style={StyleSheet.absoluteFill}
                        facing={facing}
                        enableTorch={enableTorch}
                    >
                        {/* Camera Grid Overlay - Clean view required */}
                        {/* Corner Reticles - 가시성 개선 (진하게) */}
                        <View className="absolute top-32 left-8 w-10 h-10 border-t-[3px] border-l-[3px] border-[#0d7ff2] rounded-tl-xl shadow-lg shadow-blue-500/30" />
                        <View className="absolute top-32 right-8 w-10 h-10 border-t-[3px] border-r-[3px] border-[#0d7ff2] rounded-tr-xl shadow-lg shadow-blue-500/30" />
                        <View className="absolute bottom-48 left-8 w-10 h-10 border-b-[3px] border-l-[3px] border-[#0d7ff2] rounded-bl-xl shadow-lg shadow-blue-500/30" />
                        <View className="absolute bottom-48 right-8 w-10 h-10 border-b-[3px] border-r-[3px] border-[#0d7ff2] rounded-br-xl shadow-lg shadow-blue-500/30" />

                        {/* Central Guide */}
                        <View className="absolute inset-0 items-center justify-center pointer-events-none pb-10">
                            <View className="w-[85%] aspect-square max-w-[340px] rounded-full border-2 border-dashed border-[#0d7ff2] items-center justify-center relative shadow-[0_0_20px_rgba(13,127,242,0.3)] bg-blue-500/5">
                                <View className="w-[45%] aspect-square rounded-full border border-[#0d7ff2]/50" />
                                <View className="absolute -top-12 bg-[#0d7ff2]/20 border border-[#0d7ff2] px-4 py-1.5 rounded-full flex-row items-center gap-1.5 backdrop-blur-md">
                                    <MaterialIcons name="build" size={14} color="#0d7ff2" />
                                    <Text className="text-[#0d7ff2] text-xs font-bold tracking-widest uppercase">SCAN</Text>
                                </View>
                            </View>
                        </View>

                        {/* Instruction Text */}
                        <View className="absolute bottom-44 w-full px-6 items-center justify-center pointer-events-none">
                            <View className="bg-black/70 px-6 py-4 rounded-2xl items-center border border-white/20 backdrop-blur-md w-full max-w-sm">
                                <Text className="text-white font-bold text-base mb-1 text-center">가이드라인에 맞춰 부품을 촬영해 주세요</Text>
                                <Text className="text-slate-300 text-xs text-center">어두운 곳에서는 플래시를 켜주세요</Text>
                            </View>
                        </View>
                    </CameraView>
                )}
            </View>

            {/* Bottom Controls Area */}
            <View
                className="absolute bottom-0 left-0 right-0 bg-[#101922] pt-8 rounded-t-[32px] border-t border-white/10 z-20 shadow-2xl"
                style={{ paddingBottom: insets.bottom + 20 }}
            >
                {capturedImage ? (
                    // Preview Mode Controls
                    <View className="flex-row items-center justify-between px-8 w-full max-w-md mx-auto">
                        <TouchableOpacity
                            onPress={retakePicture}
                            className="flex-1 bg-[#1e2936] py-4 rounded-xl items-center mr-3 active:scale-95"
                            disabled={isAnalyzing}
                        >
                            <Text className="text-slate-300 font-bold">재촬영</Text>
                        </TouchableOpacity>

                        <TouchableOpacity
                            onPress={analyzeImage}
                            className="flex-[2] bg-[#0d7ff2] py-4 rounded-xl items-center flex-row justify-center gap-2 active:scale-95 shadow-lg shadow-blue-500/20"
                            disabled={isAnalyzing}
                        >
                            {isAnalyzing ? (
                                <ActivityIndicator color="white" size="small" />
                            ) : (
                                <>
                                    <MaterialIcons name="check" size={20} color="white" />
                                    <Text className="text-white font-bold text-lg">진단 시작</Text>
                                </>
                            )}
                        </TouchableOpacity>
                    </View>
                ) : (
                    // Camera Mode Controls
                    <View className="flex-row items-center justify-between max-w-sm mx-auto w-full px-8">
                        {/* Flash Button */}
                        <TouchableOpacity
                            className="items-center gap-2"
                            onPress={toggleFlash}
                        >
                            <View className={`w-12 h-12 rounded-full border border-white/10 items-center justify-center active:bg-white/20 ${enableTorch ? 'bg-yellow-500/20 border-yellow-500' : 'bg-[#1e2936]'}`}>
                                <MaterialIcons name={enableTorch ? "flash-on" : "flash-off"} size={22} color={enableTorch ? "#fbbf24" : "white"} />
                            </View>
                            <Text className={`text-[11px] font-medium tracking-wide ${enableTorch ? 'text-yellow-500' : 'text-slate-400'}`}>플래시</Text>
                        </TouchableOpacity>

                        {/* Shutter Button */}
                        <TouchableOpacity
                            className="relative items-center justify-center active:scale-95 transition-all -mt-4"
                            onPress={takePicture}
                        >
                            <View className="w-20 h-20 rounded-full border-[3px] border-white/20 items-center justify-center bg-[#101922]">
                                <View className="w-16 h-16 rounded-full bg-[#0d7ff2] shadow-lg shadow-blue-500/40 border-[3px] border-[#1e2936]" />
                            </View>
                        </TouchableOpacity>

                        {/* Switch Camera */}
                        <TouchableOpacity
                            className="items-center gap-2"
                            onPress={toggleCameraFacing}
                        >
                            <View className="w-12 h-12 rounded-full bg-[#1e2936] border border-white/10 items-center justify-center active:bg-white/20">
                                <MaterialIcons name="flip-camera-ios" size={22} color="white" />
                            </View>
                            <Text className="text-[11px] text-slate-400 font-medium tracking-wide">전환</Text>
                        </TouchableOpacity>
                    </View>
                )}
            </View>
        </View>
    );
}
