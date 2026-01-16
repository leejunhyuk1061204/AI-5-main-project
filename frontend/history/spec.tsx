import React from 'react';
import { View, Text, TouchableOpacity, ScrollView, Image, Dimensions, Platform } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { LinearGradient } from 'expo-linear-gradient';

const CAR_IMAGE_URL = "https://lh3.googleusercontent.com/aida-public/AB6AXuAfxrTBxNiA6HuulRPAzDW39a_qn078fKlEXJhWCyJFUyNsZOwXeGVRzjuHZ2XlTHe8b9Px1_yQWi-8yW0E8CcSZY9rQ5gLXH0W8BSPB6c4mbB2XsCt76Hmt-ePDsB16K-3V32TdUNAO2WYetQzPAQjnUMXBmnoADau4MHNrMoEUVgP7VezAGWegsNv1C8o3DOJYw2fy95661KeEYhvvmFskgPtpk4FgJPJBoVyXZBTSKPfv-jrFTXyKLFElCUqqp6Bvel6S2FFqti-";

export default function Spec() {
    const navigation = useNavigation();
    const insets = useSafeAreaInsets();

    return (
        <View className="flex-1 bg-[#101922]">
            <StatusBar style="light" />

            {/* Background Gradient Removed */}

            {/* Header */}
            <View
                style={{ paddingTop: insets.top }}
                className="z-50 px-4 pb-2 border-b border-white/5 bg-[#101922]/80"
            >
                <View className="flex-row items-center justify-between h-14">
                    <TouchableOpacity
                        onPress={() => navigation.goBack()}
                        className="w-10 h-10 items-center justify-center rounded-full active:bg-white/10"
                    >
                        <MaterialIcons name="arrow-back-ios-new" size={20} color="white" />
                    </TouchableOpacity>

                    <Text className="text-white text-lg font-bold flex-1 text-center mr-10">
                        차량 상세 제원 정보
                    </Text>
                </View>
            </View>

            <ScrollView
                className="flex-1"
                contentContainerStyle={{ paddingBottom: 120 }}
                showsVerticalScrollIndicator={false}
            >
                <View className="p-4 flex-col gap-6">

                    {/* Hero Card */}
                    <View className="relative w-full overflow-hidden rounded-2xl bg-[#121826]/60 border border-white/10">
                        {/* Glow Effect Removed */}

                        <View className="w-full h-56 relative bg-white/5">
                            <LinearGradient
                                colors={['transparent', '#121826']}
                                className="absolute inset-0 z-10"
                            />
                            <Image
                                source={{ uri: CAR_IMAGE_URL }}
                                className="w-full h-full"
                                resizeMode="contain"
                            />
                            <View className="absolute top-4 right-4 z-20 bg-black/40 px-3 py-1 rounded-full border border-white/10">
                                <Text className="text-xs font-medium text-white/80">2024 Model</Text>
                            </View>
                        </View>

                        <View className="p-5 -mt-6 relative z-20">
                            <View className="flex-row items-center gap-2 mb-2">
                                <View className="h-6 w-6 rounded-full bg-white items-center justify-center">
                                    <MaterialIcons name="local-taxi" size={16} color="black" />
                                </View>
                                <Text className="text-primary text-sm font-bold tracking-wider uppercase">Genesis</Text>
                            </View>
                            <Text className="text-white text-3xl font-bold mb-1">Genesis G80</Text>
                            <Text className="text-gray-400 text-sm font-normal">2.5 Gasoline Turbo AWD • Sport Package</Text>
                        </View>
                    </View>

                    {/* Performance Grid */}
                    <View>
                        <View className="flex-row items-center gap-2 mb-4">
                            <MaterialIcons name="bolt" size={24} color="#0d7ff2" />
                            <Text className="text-white/90 text-lg font-bold">
                                성능 정보 <Text className="text-sm font-normal text-gray-500">(Performance)</Text>
                            </Text>
                        </View>

                        <View className="flex-row flex-wrap gap-3">
                            {/* Item 1 */}
                            <View className="w-[48%] bg-white/5 border border-white/5 rounded-xl p-4 gap-3">
                                <View className="items-start">
                                    <MaterialIcons name="water-drop" size={24} color="#94a3b8" />
                                </View>
                                <View>
                                    <Text className="text-gray-400 text-xs mb-1">배기량</Text>
                                    <Text className="text-white text-xl font-bold">2,497 <Text className="text-sm font-normal text-gray-500">cc</Text></Text>
                                </View>
                            </View>

                            {/* Item 2 */}
                            <View className="w-[48%] bg-white/5 border border-white/5 rounded-xl p-4 gap-3">
                                <View className="items-start">
                                    <MaterialIcons name="speed" size={24} color="#94a3b8" />
                                </View>
                                <View>
                                    <Text className="text-gray-400 text-xs mb-1">최대 출력</Text>
                                    <Text className="text-white text-xl font-bold">304 <Text className="text-sm font-normal text-gray-500">hp</Text></Text>
                                </View>
                            </View>

                            {/* Item 3 */}
                            <View className="w-[48%] bg-white/5 border border-white/5 rounded-xl p-4 gap-3">
                                <View className="items-start">
                                    <MaterialIcons name="local-gas-station" size={24} color="#94a3b8" />
                                </View>
                                <View>
                                    <Text className="text-gray-400 text-xs mb-1">연비</Text>
                                    <Text className="text-white text-xl font-bold">10.8 <Text className="text-sm font-normal text-gray-500">km/ℓ</Text></Text>
                                </View>
                            </View>

                            {/* Item 4 */}
                            <View className="w-[48%] bg-white/5 border border-white/5 rounded-xl p-4 gap-3">
                                <View className="items-start">
                                    <MaterialIcons name="hub" size={24} color="#94a3b8" />
                                </View>
                                <View>
                                    <Text className="text-gray-400 text-xs mb-1">구동 방식</Text>
                                    <Text className="text-white text-xl font-bold">AWD</Text>
                                </View>
                            </View>
                        </View>
                    </View>

                    {/* Tire Specs */}
                    <View>
                        <View className="flex-row items-center gap-2 mb-4">
                            <MaterialIcons name="tire-repair" size={24} color="#0d7ff2" />
                            <Text className="text-white/90 text-lg font-bold">
                                타이어 규격 <Text className="text-sm font-normal text-gray-500">(Tires)</Text>
                            </Text>
                        </View>

                        <View className="bg-[#121826]/60 border border-white/5 rounded-xl overflow-hidden">
                            <View className="flex-row items-center justify-between p-4 border-b border-white/5 active:bg-white/5">
                                <View className="flex-row items-center gap-3">
                                    <View className="bg-[#16212b] px-2 py-1.5 rounded-lg border border-white/5 min-w-[50px] items-center">
                                        <Text className="text-[10px] font-bold text-primary">FRONT</Text>
                                    </View>
                                    <Text className="text-gray-300 text-sm">프론트 타이어</Text>
                                </View>
                                <Text className="text-white font-bold text-lg">245/40R19</Text>
                            </View>

                            <View className="flex-row items-center justify-between p-4 active:bg-white/5">
                                <View className="flex-row items-center gap-3">
                                    <View className="bg-[#16212b] px-2 py-1.5 rounded-lg border border-white/5 min-w-[50px] items-center">
                                        <Text className="text-[10px] font-bold text-primary">REAR</Text>
                                    </View>
                                    <Text className="text-gray-300 text-sm">리어 타이어</Text>
                                </View>
                                <Text className="text-white font-bold text-lg">275/35R19</Text>
                            </View>
                        </View>
                    </View>

                    {/* Dimensions Specs */}
                    <View>
                        <View className="flex-row items-center gap-2 mb-4">
                            <MaterialIcons name="square-foot" size={24} color="#0d7ff2" />
                            <Text className="text-white/90 text-lg font-bold">
                                치수 정보 <Text className="text-sm font-normal text-gray-500">(Dimensions)</Text>
                            </Text>
                        </View>

                        <View className="flex-row gap-3">
                            <View className="flex-1 bg-white/5 border border-white/5 rounded-xl p-4 items-center justify-center gap-1">
                                <Text className="text-xs text-gray-400">전장 (Length)</Text>
                                <Text className="text-white font-bold text-lg">4,995 <Text className="text-xs font-normal text-gray-500">mm</Text></Text>
                                <View className="w-full h-1 bg-white/10 mt-2 rounded-full overflow-hidden">
                                    <View className="bg-primary w-[90%] h-full rounded-full" />
                                </View>
                            </View>

                            <View className="flex-1 bg-white/5 border border-white/5 rounded-xl p-4 items-center justify-center gap-1">
                                <Text className="text-xs text-gray-400">전폭 (Width)</Text>
                                <Text className="text-white font-bold text-lg">1,925 <Text className="text-xs font-normal text-gray-500">mm</Text></Text>
                                <View className="w-full h-1 bg-white/10 mt-2 rounded-full overflow-hidden">
                                    <View className="bg-primary w-[70%] h-full rounded-full" />
                                </View>
                            </View>

                            <View className="flex-1 bg-white/5 border border-white/5 rounded-xl p-4 items-center justify-center gap-1">
                                <Text className="text-xs text-gray-400">전고 (Height)</Text>
                                <Text className="text-white font-bold text-lg">1,465 <Text className="text-xs font-normal text-gray-500">mm</Text></Text>
                                <View className="w-full h-1 bg-white/10 mt-2 rounded-full overflow-hidden">
                                    <View className="bg-primary w-[50%] h-full rounded-full" />
                                </View>
                            </View>
                        </View>
                    </View>

                </View>
            </ScrollView>
        </View>
    );
}
