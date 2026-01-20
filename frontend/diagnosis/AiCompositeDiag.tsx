import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, TextInput, Platform, Image } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { LinearGradient } from 'expo-linear-gradient';

export default function AiCompositeDiag() {
    const navigation = useNavigation<any>();
    const [messages, setMessages] = useState([
        {
            id: 1,
            type: 'ai',
            text: '안녕하세요! 차량 상태의 정밀 분석을 위해 시스템에 연결되었습니다.',
            isFirst: true
        },
        {
            id: 2,
            type: 'ai',
            text: '정확한 진단을 위해 몇 가지 데이터가 필요합니다. 먼저 엔진 시동음을 녹음할까요?',
            highlight: '엔진 시동음',
            isFirst: false
        }
    ]);

    return (
        <View className="flex-1 bg-background-dark">
            <StatusBar style="light" />

            {/* Background Effects Removed */}

            {/* Header */}
            <SafeAreaView edges={['top']} className="z-20 bg-[#0c0e12]/80 border-b border-white/5 backdrop-blur-md">
                <View className="flex-row items-center justify-between px-4 pb-4 pt-2">
                    <TouchableOpacity
                        onPress={() => navigation.goBack()}
                        className="p-2 rounded-full active:bg-white/10"
                    >
                        <MaterialIcons name="arrow-back-ios" size={20} color="rgba(255,255,255,0.5)" />
                    </TouchableOpacity>

                    <View className="items-center">
                        <View className="flex-row items-center gap-2">
                            <Text className="text-white/90 text-[17px] font-bold tracking-tight">
                                AI 진단 어시스턴트
                            </Text>
                            <View className="relative w-2 h-2">
                                <View className="absolute w-full h-full rounded-full bg-accent-blue opacity-40 animate-pulse" />
                                <View className="w-2 h-2 rounded-full bg-accent-blue" />
                            </View>
                        </View>
                        <Text className="text-[10px] text-muted-blue tracking-[0.2em] font-semibold uppercase mt-0.5">
                            Active Monitoring
                        </Text>
                    </View>

                    <TouchableOpacity className="p-2 rounded-full active:bg-white/10">
                        <MaterialIcons name="more-horiz" size={24} color="rgba(255,255,255,0.5)" />
                    </TouchableOpacity>
                </View>
            </SafeAreaView>

            {/* Chat Area */}
            <ScrollView
                className="flex-1 px-5 pt-6"
                contentContainerStyle={{ paddingBottom: 150 }}
                showsVerticalScrollIndicator={false}
            >
                {/* Date Divider */}
                <View className="items-center mb-6">
                    <Text className="text-[11px] text-white/20 font-medium tracking-widest">
                        2024.05.21 TUE
                    </Text>
                </View>

                {/* AI Tech Icon Row */}
                <View className="flex-row items-start gap-3 max-w-[88%] mb-2">
                    <View className="mt-1">
                        <View className="w-9 h-9 rounded-xl bg-navy-dark border border-white/10 items-center justify-center">
                            <MaterialIcons name="analytics" size={20} color="#3d7eff" />
                        </View>
                    </View>
                    <View className="gap-1.5 shrink">
                        <Text className="text-muted-blue text-[11px] font-bold ml-1 tracking-tight">
                            AI DIAGNOSTICS
                        </Text>
                        <View className="bg-[#121a26]/60 border border-white/5 rounded-2xl rounded-tl-none px-4 py-3.5">
                            <Text className="text-[15px] text-white/80 leading-relaxed">
                                {messages[0].text}
                            </Text>
                        </View>
                    </View>
                </View>

                {/* Follow-up Message */}
                <View className="flex-row items-start gap-3 max-w-[88%]">
                    <View className="w-9 h-9" /> {/* Spacer for alignment */}
                    <View className="gap-1.5 shrink -mt-2">
                        <View className="bg-[#121a26]/60 border border-white/5 border-l-2 border-l-accent-blue/40 rounded-2xl rounded-tl-none px-4 py-3.5 shadow-sm">
                            <Text className="text-[15px] text-white/90 font-medium leading-relaxed">
                                정확한 진단을 위해 몇 가지 데이터가 필요합니다. 먼저 <Text className="text-accent-blue font-bold">엔진 시동음</Text>을 녹음할까요?
                            </Text>
                        </View>
                    </View>
                </View>
            </ScrollView>

            {/* Bottom Actions Area */}
            <View className="absolute bottom-0 left-0 right-0 z-20">
                {/* Action Buttons Container */}
                <View className="flex-row justify-between px-5 pb-5 gap-3">
                    <TouchableOpacity
                        onPress={() => navigation.navigate('EngineSoundDiag')}
                        className="flex-1 h-[100px] p-3 rounded-2xl bg-[#121a26]/60 border border-white/5 justify-between active:scale-95 overflow-hidden relative group"
                    >
                        <View className="w-8 h-8 rounded-lg bg-accent-blue/10 items-center justify-center mb-1">
                            <MaterialIcons name="mic" size={20} color="#3d7eff" />
                        </View>
                        <Text className="text-[12px] font-bold text-white/90 leading-tight">녹음 시작</Text>
                        <View className="absolute bottom-0 left-0 h-[2px] w-full bg-accent-blue opacity-50" />
                    </TouchableOpacity>

                    <TouchableOpacity
                        onPress={() => navigation.navigate('Filming')}
                        className="flex-1 h-[100px] p-3 rounded-2xl bg-[#121a26]/60 border border-white/5 justify-between active:scale-95 overflow-hidden relative"
                    >
                        <View className="w-8 h-8 rounded-lg bg-accent-blue/10 items-center justify-center mb-1">
                            <MaterialIcons name="camera-alt" size={20} color="#3d7eff" />
                        </View>
                        <Text className="text-[12px] font-bold text-white/90 leading-tight">사진 촬영</Text>
                        <View className="absolute bottom-0 left-0 h-[2px] w-full bg-accent-blue opacity-50" />
                    </TouchableOpacity>

                    <TouchableOpacity
                        // Assuming ActiveReg is the OBD connection flow based on context
                        onPress={() => navigation.navigate('ActiveReg')}
                        className="flex-1 h-[100px] p-3 rounded-2xl bg-[#121a26]/60 border border-white/5 justify-between active:scale-95 overflow-hidden relative"
                    >
                        <View className="w-8 h-8 rounded-lg bg-accent-blue/10 items-center justify-center mb-1">
                            <MaterialCommunityIcons name="car-connected" size={20} color="#3d7eff" />
                        </View>
                        <Text className="text-[12px] font-bold text-white/90 leading-tight">OBD 스캔</Text>
                        <View className="absolute bottom-0 left-0 h-[2px] w-full bg-accent-blue opacity-50" />
                    </TouchableOpacity>
                </View>

                {/* Input Area */}
                <SafeAreaView edges={['bottom']} className="bg-background-dark/95 border-t border-white/5 px-4 pt-4 pb-2">
                    <View className="flex-row items-center gap-2 bg-navy-dark/50 border border-white/10 rounded-[24px] p-1.5 pl-4 mb-2">
                        <TouchableOpacity className="w-8 h-8 items-center justify-center rounded-full active:bg-white/5">
                            <MaterialIcons name="add" size={24} color="rgba(255,255,255,0.3)" />
                        </TouchableOpacity>

                        <TextInput
                            placeholder="AI에게 질문해보세요..."
                            placeholderTextColor="rgba(255,255,255,0.2)"
                            className="flex-1 text-[15px] text-white py-2"
                        />

                        <TouchableOpacity className="w-8 h-8 items-center justify-center rounded-full active:bg-white/5 mr-1">
                            <MaterialIcons name="mic" size={22} color="rgba(255,255,255,0.3)" />
                        </TouchableOpacity>

                        <TouchableOpacity className="w-10 h-10 bg-accent-blue/90 rounded-full items-center justify-center shadow-lg active:scale-95">
                            <MaterialIcons name="arrow-upward" size={20} color="white" />
                        </TouchableOpacity>
                    </View>
                    <View className="w-32 h-1 bg-white/10 rounded-full mx-auto mb-2" />
                </SafeAreaView>
            </View>
        </View>
    );
}
