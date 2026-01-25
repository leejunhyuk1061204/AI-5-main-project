import React from 'react';
import { View, Text, TouchableOpacity, Image } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import BaseScreen from '../components/layout/BaseScreen';

export default function VisualDiagnosis() {
    const navigation = useNavigation();
    const route = useRoute<any>();
    const { diagnosisResult, capturedImage } = route.params || {};

    // API 이미지 URL이 없으면 로컬 촬영 이미지(capturedImage)를 사용
    const displayImage = diagnosisResult?.imageUrl || capturedImage;

    const HeaderCustom = (
        <View className="flex-row items-center justify-between px-4 py-3 border-b border-white/5">
            <TouchableOpacity
                onPress={() => navigation.goBack()}
                className="w-10 h-10 items-center justify-center rounded-full active:bg-white/10"
            >
                <MaterialIcons name="arrow-back-ios" size={20} color="white" />
            </TouchableOpacity>
            <Text className="text-white text-lg font-bold">진단 결과</Text>
            <View className="w-10" />
        </View>
    );

    return (
        <BaseScreen
            header={HeaderCustom}
            scrollable={true}
            padding={false}
        >
            {/* Image Viewer */}
            <View className="w-full aspect-[4/3] bg-black mb-6 relative">
                {displayImage ? (
                    <Image
                        source={{ uri: displayImage }}
                        className="w-full h-full"
                        resizeMode="contain"
                    />
                ) : (
                    <View className="flex-1 items-center justify-center">
                        <MaterialIcons name="image-not-supported" size={48} color="gray" />
                        <Text className="text-gray-500 mt-2">이미지를 불러올 수 없습니다.</Text>
                    </View>
                )}

                {/* Status Overlay */}
                <View className="absolute bottom-4 left-4 right-4 flex-row justify-between items-end">
                    <View className="bg-black/60 px-3 py-1.5 rounded-lg border border-white/10 backdrop-blur-md">
                        <Text className="text-white font-bold text-sm">
                            신뢰도: {Math.round((diagnosisResult?.confidence || 0) * 100)}%
                        </Text>
                    </View>
                </View>
            </View>

            {/* Analysis Result */}
            <View className="px-5">
                <View className="bg-[#1b2127] rounded-2xl p-6 border border-white/10 mb-6">
                    <View className="flex-row items-center gap-3 mb-4">
                        <View className={`w-10 h-10 rounded-full items-center justify-center ${diagnosisResult?.result === 'NORMAL' ? 'bg-green-500/20' : 'bg-red-500/20'}`}>
                            <MaterialIcons
                                name={diagnosisResult?.result === 'NORMAL' ? "check-circle" : "warning"}
                                size={24}
                                color={diagnosisResult?.result === 'NORMAL' ? "#4ade80" : "#ef4444"}
                            />
                        </View>
                        <View>
                            <Text className="text-sm text-slate-400 font-medium">진단 결과</Text>
                            <Text className="text-xl font-bold text-white mt-0.5">
                                {diagnosisResult?.result === 'NORMAL' ? '정상' : '이상 발견'}
                            </Text>
                        </View>
                    </View>

                    <View className="h-[1px] bg-white/10 w-full mb-4" />

                    <Text className="text-slate-300 leading-6 text-base">
                        {diagnosisResult?.description || "분석된 진단 내용이 없습니다."}
                    </Text>
                </View>

                {/* Parts Details */}
                {diagnosisResult?.parts && diagnosisResult.parts.length > 0 && (
                    <View className="mb-6">
                        <Text className="text-white font-bold text-lg mb-4 px-1">부품별 상세 분석</Text>
                        {diagnosisResult.parts.map((part: any, index: number) => (
                            <View key={index} className="flex-row items-center justify-between bg-[#1b2127] p-4 rounded-xl border border-white/5 mb-3">
                                <Text className="text-slate-300 font-medium">{part.name}</Text>
                                <View className={`px-2.5 py-1 rounded-md ${part.status === 'NORMAL' ? 'bg-green-500/10' :
                                    part.status === 'WARNING' ? 'bg-yellow-500/10' : 'bg-red-500/10'
                                    }`}>
                                    <Text className={`text-xs font-bold ${part.status === 'NORMAL' ? 'text-green-500' :
                                        part.status === 'WARNING' ? 'text-yellow-500' : 'text-red-500'
                                        }`}>
                                        {part.status}
                                    </Text>
                                </View>
                            </View>
                        ))}
                    </View>
                )}

                <TouchableOpacity
                    onPress={() => navigation.goBack()}
                    className="w-full bg-[#0d7ff2] py-4 rounded-xl items-center active:scale-95 shadow-lg shadow-blue-500/20 mb-10"
                >
                    <Text className="text-white font-bold text-base">확인</Text>
                </TouchableOpacity>
            </View>
        </BaseScreen>
    );
}
