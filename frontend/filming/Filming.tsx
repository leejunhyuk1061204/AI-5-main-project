import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, Dimensions, StyleSheet } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { LinearGradient } from 'expo-linear-gradient';

const { width, height } = Dimensions.get('window');

export default function Filming() {
    const navigation = useNavigation();
    const insets = useSafeAreaInsets();
    const [permission, requestPermission] = useCameraPermissions();
    const [scanned, setScanned] = useState(false);

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
                className="flex-row items-start justify-between px-4 z-20 absolute top-0 left-0 right-0 bg-transparent"
                style={{ paddingTop: insets.top + 10 }}
            >
                <TouchableOpacity
                    onPress={() => navigation.goBack()}
                    className="w-10 h-10 items-center justify-center rounded-full active:bg-white/10"
                >
                    <MaterialIcons name="arrow-back-ios" size={20} color="white" />
                </TouchableOpacity>

                <View className="items-center">
                    <Text className="text-white text-lg font-bold">AI 복합 진단</Text>
                </View>

                <TouchableOpacity className="w-10 h-10 items-center justify-center rounded-full active:bg-white/10">
                    <MaterialIcons name="help-outline" size={24} color="white" />
                </TouchableOpacity>
            </View>

            {/* Main Content (Camera View) */}
            <View className="absolute inset-0 z-0 bg-black">
                <CameraView
                    style={StyleSheet.absoluteFill}
                    facing="back"
                >
                    {/* Camera Grid Overlay - Clean view required */}

                    {/* Corner Reticles - 가시성 개선 (진하게) */}
                    <View className="absolute top-32 left-8 w-10 h-10 border-t-[3px] border-l-[3px] border-[#0d7ff2] rounded-tl-xl shadow-lg shadow-blue-500/30" />
                    <View className="absolute top-32 right-8 w-10 h-10 border-t-[3px] border-r-[3px] border-[#0d7ff2] rounded-tr-xl shadow-lg shadow-blue-500/30" />
                    <View className="absolute bottom-48 left-8 w-10 h-10 border-b-[3px] border-l-[3px] border-[#0d7ff2] rounded-bl-xl shadow-lg shadow-blue-500/30" />
                    <View className="absolute bottom-48 right-8 w-10 h-10 border-b-[3px] border-r-[3px] border-[#0d7ff2] rounded-br-xl shadow-lg shadow-blue-500/30" />

                    {/* Central Guide (Tire Scan) - 스캔 라인 제거 및 가시성 개선 */}
                    <View className="absolute inset-0 items-center justify-center pointer-events-none pb-10">
                        <View className="w-[85%] aspect-square max-w-[340px] rounded-full border-2 border-dashed border-[#0d7ff2] items-center justify-center relative shadow-[0_0_20px_rgba(13,127,242,0.3)] bg-blue-500/5">
                            {/* Inner Hub Guide */}
                            <View className="w-[45%] aspect-square rounded-full border border-[#0d7ff2]/50" />

                            {/* Floating Label */}
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
            </View>

            {/* Bottom Controls Area */}
            <View
                className="absolute bottom-0 left-0 right-0 bg-[#101922] pt-8 rounded-t-[32px] border-t border-white/10 z-20 shadow-2xl"
                style={{ paddingBottom: insets.bottom + 20 }}
            >
                <View className="flex-row items-center justify-between max-w-sm mx-auto w-full px-8">
                    {/* Flash Button */}
                    <TouchableOpacity className="items-center gap-2">
                        <View className="w-12 h-12 rounded-full bg-[#1e2936] border border-white/10 items-center justify-center active:bg-white/20">
                            <MaterialIcons name="flash-on" size={22} color="white" />
                        </View>
                        <Text className="text-[11px] text-slate-400 font-medium tracking-wide">플래시</Text>
                    </TouchableOpacity>

                    {/* Shutter Button - Design Update */}
                    <TouchableOpacity className="relative items-center justify-center active:scale-95 transition-all -mt-4">
                        <View className="w-20 h-20 rounded-full border-[3px] border-white/20 items-center justify-center bg-[#101922]">
                            <View className="w-16 h-16 rounded-full bg-[#0d7ff2] shadow-lg shadow-blue-500/40 border-[3px] border-[#1e2936]" />
                        </View>
                    </TouchableOpacity>

                    {/* Switch Mode/Camera */}
                    <TouchableOpacity className="items-center gap-2">
                        <View className="w-12 h-12 rounded-full bg-[#1e2936] border border-white/10 items-center justify-center active:bg-white/20">
                            <MaterialIcons name="flip-camera-ios" size={22} color="white" />
                        </View>
                        <Text className="text-[11px] text-slate-400 font-medium tracking-wide">전환</Text>
                    </TouchableOpacity>
                </View>
            </View>
        </View>
    );
}
