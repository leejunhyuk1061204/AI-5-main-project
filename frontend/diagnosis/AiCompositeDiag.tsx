import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, TextInput } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import BottomNav from '../nav/BottomNav';
import Header from '../header/Header';

export default function AiCompositeDiag() {
    const navigation = useNavigation<any>();
    const route = useRoute<any>();
    const [messages, setMessages] = useState([
        {
            id: 1,
            type: 'ai',
            text: '안녕하세요! 차량 상태의 정밀 분석을 위해 시스템에 연결되었습니다.',
            isFirst: true
        },
    ]);

    React.useEffect(() => {
        if (route.params?.diagnosisResult) {
            const result = route.params.diagnosisResult;
            const newMsg = {
                id: messages.length + 1,
                type: 'ai',
                text: `진단이 완료되었습니다.\n결과: ${result.result === 'NORMAL' ? '정상' : '이상 감지'}\n\n${result.description}`,
                isFirst: false
            };
            setMessages(prev => [...prev, newMsg]);
            navigation.setParams({ diagnosisResult: null });
        }
    }, [route.params?.diagnosisResult]);

    return (
        <View className="flex-1 bg-background-dark">
            <StatusBar style="light" />
            <SafeAreaView edges={['top']}>
                <Header />
            </SafeAreaView>
            <ScrollView className="flex-1 px-5 pt-6" contentContainerStyle={{ paddingBottom: 180 }} showsVerticalScrollIndicator={false}>
                <View className="items-center mb-6">
                    <Text className="text-[11px] text-white/20 font-medium tracking-widest">2024.05.21 TUE</Text>
                </View>
                <View className="flex-row items-start gap-3 max-w-[88%] mb-2">
                    <View className="mt-1">
                        <View className="w-9 h-9 rounded-xl bg-[#1e293b] border border-white/20 items-center justify-center shadow-sm">
                            <MaterialIcons name="analytics" size={20} color="#3d7eff" />
                        </View>
                    </View>
                    <View className="gap-1.5 shrink">
                        <Text className="text-slate-400 text-[11px] font-bold ml-1 tracking-tight">AI DIAGNOSTICS</Text>
                        <View className="bg-[#1e293b] border border-white/10 rounded-2xl rounded-tl-none px-4 py-3.5 shadow-sm">
                            <Text className="text-[15px] text-white/95 leading-relaxed">{messages[0].text}</Text>
                        </View>
                    </View>
                </View>
                <View className="flex-row items-start gap-3 max-w-[88%]">
                    <View className="w-9 h-9" />
                    <View className="gap-1.5 shrink -mt-2">
                        <View className="bg-[#1e293b] border border-white/10 border-l-2 border-l-accent-blue rounded-2xl rounded-tl-none px-4 py-3.5 shadow-sm">
                            <Text className="text-[15px] text-white/95 font-medium leading-relaxed">
                                정확한 진단을 위해 몇 가지 데이터가 필요합니다. 먼저 <Text className="text-[#60a5fa] font-bold">엔진 시동음</Text>을 녹음할까요?
                            </Text>
                        </View>
                    </View>
                </View>
            </ScrollView>
            <View className="absolute left-0 right-0 z-20" style={{ bottom: 80 }}>
                <View className="flex-row justify-between px-5 pb-5 gap-3">
                    <TouchableOpacity onPress={() => navigation.navigate('EngineSoundDiag', { from: 'chatbot' })} className="flex-1 h-[100px] p-3 rounded-2xl bg-[#1e293b] border border-white/10 justify-between active:scale-95 overflow-hidden relative group">
                        <View className="w-8 h-8 rounded-lg bg-[#0d7ff2]/20 items-center justify-center mb-1">
                            <MaterialIcons name="mic" size={20} color="#60a5fa" />
                        </View>
                        <Text className="text-[12px] font-bold text-white/95 leading-tight">녹음 시작</Text>
                        <View className="absolute bottom-0 left-0 h-[3px] w-full bg-[#3b82f6]" />
                    </TouchableOpacity>
                    <TouchableOpacity onPress={() => navigation.navigate('Filming', { from: 'chatbot' })} className="flex-1 h-[100px] p-3 rounded-2xl bg-[#1e293b] border border-white/10 justify-between active:scale-95 overflow-hidden relative">
                        <View className="w-8 h-8 rounded-lg bg-[#0d7ff2]/20 items-center justify-center mb-1">
                            <MaterialIcons name="camera-alt" size={20} color="#60a5fa" />
                        </View>
                        <Text className="text-[12px] font-bold text-white/95 leading-tight">사진 촬영</Text>
                        <View className="absolute bottom-0 left-0 h-[3px] w-full bg-[#3b82f6]" />
                    </TouchableOpacity>
                    <TouchableOpacity onPress={() => navigation.navigate('ActiveReg')} className="flex-1 h-[100px] p-3 rounded-2xl bg-[#1e293b] border border-white/10 justify-between active:scale-95 overflow-hidden relative">
                        <View className="w-8 h-8 rounded-lg bg-[#0d7ff2]/20 items-center justify-center mb-1">
                            <MaterialCommunityIcons name="car-connected" size={20} color="#60a5fa" />
                        </View>
                        <Text className="text-[12px] font-bold text-white/95 leading-tight">OBD 스캔</Text>
                        <View className="absolute bottom-0 left-0 h-[3px] w-full bg-[#3b82f6]" />
                    </TouchableOpacity>
                </View>
                <SafeAreaView edges={['bottom']} className="bg-background-dark/95 border-t border-white/10 px-4 pt-4 pb-2">
                    <View className="flex-row items-center gap-2 bg-[#1e293b] border border-white/20 rounded-[24px] p-1.5 pl-4 mb-2">
                        <TouchableOpacity className="w-8 h-8 items-center justify-center rounded-full active:bg-white/10">
                            <MaterialIcons name="add" size={24} color="#94a3b8" />
                        </TouchableOpacity>
                        <TextInput placeholder="AI에게 질문해보세요..." placeholderTextColor="#94a3b8" className="flex-1 text-[15px] text-white py-2" />
                        <TouchableOpacity className="w-8 h-8 items-center justify-center rounded-full active:bg-white/10 mr-1">
                            <MaterialIcons name="mic" size={22} color="#94a3b8" />
                        </TouchableOpacity>
                        <TouchableOpacity className="w-10 h-10 bg-[#3b82f6] rounded-full items-center justify-center shadow-lg active:scale-95">
                            <MaterialIcons name="arrow-upward" size={20} color="white" />
                        </TouchableOpacity>
                    </View>
                </SafeAreaView>
            </View>
            <BottomNav />
        </View>
    );
}
