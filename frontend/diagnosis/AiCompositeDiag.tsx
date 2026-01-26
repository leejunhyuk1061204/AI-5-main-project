import React, { useState, useRef, useEffect } from 'react';
import { View, Text, TouchableOpacity, ScrollView, TextInput, Keyboard, Platform } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import BottomNav from '../nav/BottomNav';
import Header from '../header/Header';
import BaseScreen from '../components/layout/BaseScreen';
import VehicleSelectModal from '../components/VehicleSelectModal';
import { useUIStore } from '../store/useUIStore';

export default function AiCompositeDiag() {
    const navigation = useNavigation<any>();
    const route = useRoute<any>();
    const insets = useSafeAreaInsets();
    const [messages, setMessages] = useState([
        {
            id: 1,
            type: 'ai',
            text: '안녕하세요! 차량 상태의 정밀 분석을 위해 시스템에 연결되었습니다.',
            isFirst: true
        },
    ]);

    // Manual diagnosis state
    const [vehicleSelectVisible, setVehicleSelectVisible] = useState(false);
    // Mock Bluetooth connection
    const [isConnected, setIsConnected] = useState(false);
    const [selectedVehicleId, setSelectedVehicleId] = useState<string | null>(null);
    const [selectedVehicleName, setSelectedVehicleName] = useState<string>('');
    const selectionRef = React.useRef(false);
    const setKeyboardVisible = useUIStore(state => state.setKeyboardVisible);
    const bottomNavVisible = useUIStore(state => state.bottomNavVisible);
    const isKeyboardVisible = useUIStore(state => state.isKeyboardVisible);
    const scrollRef = useRef<ScrollView>(null);

    // Auto-scroll logic
    const scrollToEnd = (animated = false) => {
        scrollRef.current?.scrollToEnd({ animated });
    };

    // Initial check on mount

    // Initial check on mount
    React.useEffect(() => {
        if (route.params?.vehicleId) {
            setSelectedVehicleId(route.params.vehicleId);
            return;
        }

        if (!isConnected && !selectedVehicleId) {
            setVehicleSelectVisible(true);
        }
    }, [isConnected, route.params?.vehicleId, selectedVehicleId]);

    const handleVehicleSelect = (vehicle: any) => {
        selectionRef.current = true;
        setSelectedVehicleId(vehicle.vehicleId);
        setSelectedVehicleName(`${vehicle.manufacturer} ${vehicle.modelName}`);
        setVehicleSelectVisible(false);

        const newMsg = {
            id: Date.now(),
            type: 'ai',
            text: `${vehicle.manufacturer} ${vehicle.modelName} 차량의 진단을 시작합니다.`,
            isFirst: false
        };
        setMessages(prev => [...prev, newMsg]);
    };

    // Diagnosis result handler
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

    const handleFocus = () => {
        // 즉각적인 하단바 숨김 트리거
        useUIStore.getState().setKeyboardVisible(true);
    };

    return (
        <BaseScreen
            header={<Header />}
            scrollable={false}
            androidKeyboardBehavior="height"
            padding={false}
            useBottomNav={true}
            footer={
                <View className="w-full bg-background-dark/95 backdrop-blur-md pt-2">
                    {/* Action Buttons - 키보드가 보일 때는 숨김 처리 */}
                    {!useUIStore.getState().isKeyboardVisible && (
                        <View className="flex-row justify-between px-5 pb-5 gap-3">
                            <TouchableOpacity onPress={() => navigation.navigate('EngineSoundDiag', { from: 'chatbot' })} className="flex-1 h-[90px] p-3 rounded-2xl bg-surface-dark border border-white/10 justify-between active:scale-95 overflow-hidden relative">
                                <View className="w-8 h-8 rounded-lg bg-primary/20 items-center justify-center mb-1">
                                    <MaterialIcons name="mic" size={20} color="#60a5fa" />
                                </View>
                                <Text className="text-[12px] font-bold text-white/95 leading-tight">녹음 시작</Text>
                                <View className="absolute bottom-0 left-0 h-[3px] w-full bg-primary" />
                            </TouchableOpacity>
                            <TouchableOpacity onPress={() => navigation.navigate('Filming', { from: 'chatbot' })} className="flex-1 h-[90px] p-3 rounded-2xl bg-surface-dark border border-white/10 justify-between active:scale-95 overflow-hidden relative">
                                <View className="w-8 h-8 rounded-lg bg-primary/20 items-center justify-center mb-1">
                                    <MaterialIcons name="camera-alt" size={20} color="#60a5fa" />
                                </View>
                                <Text className="text-[12px] font-bold text-white/95 leading-tight">사진 촬영</Text>
                                <View className="absolute bottom-0 left-0 h-[3px] w-full bg-primary" />
                            </TouchableOpacity>
                            <TouchableOpacity onPress={() => navigation.navigate('ActiveReg')} className="flex-1 h-[90px] p-3 rounded-2xl bg-surface-dark border border-white/10 justify-between active:scale-95 overflow-hidden relative">
                                <View className="w-8 h-8 rounded-lg bg-primary/20 items-center justify-center mb-1">
                                    <MaterialCommunityIcons name="car-connected" size={20} color="#60a5fa" />
                                </View>
                                <Text className="text-[12px] font-bold text-white/95 leading-tight">OBD 스캔</Text>
                                <View className="absolute bottom-0 left-0 h-[3px] w-full bg-primary" />
                            </TouchableOpacity>
                        </View>
                    )}

                    {/* Input Area */}
                    <View
                        className="px-5 pb-4"
                        style={{
                            minHeight: 60, // 레이아웃 지원
                        }}
                    >
                        <View className="flex-row items-center gap-2 bg-[#1e293b] border border-white/20 rounded-[24px] p-1.5 pl-4 shadow-xl">
                            <TouchableOpacity className="w-8 h-8 items-center justify-center rounded-full active:bg-white/10">
                                <MaterialIcons name="add" size={24} color="#94a3b8" />
                            </TouchableOpacity>
                            <TextInput
                                placeholder="AI에게 질문해보세요..."
                                placeholderTextColor="#94a3b8"
                                className="flex-1 text-[15px] text-white py-2"
                                onFocus={handleFocus}
                            />
                            <TouchableOpacity className="w-8 h-8 items-center justify-center rounded-full active:bg-white/10 mr-1">
                                <MaterialIcons name="mic" size={22} color="#94a3b8" />
                            </TouchableOpacity>
                            <TouchableOpacity className="w-10 h-10 bg-primary rounded-full items-center justify-center shadow-lg active:scale-95">
                                <MaterialIcons name="arrow-upward" size={20} color="white" />
                            </TouchableOpacity>
                        </View>
                    </View>
                </View>
            }
        >
            <View className="flex-1">
                <View className="items-center mt-4">
                    <Text className="text-[11px] text-white/20 font-medium tracking-widest">
                        {new Date().toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit', weekday: 'short' }).toUpperCase()}
                    </Text>
                </View>

                {/* Selected Vehicle Info + Change Button - FIXED TOP */}
                <View className="px-5 mt-2">
                    {selectedVehicleId && (
                        <View className="mb-4 flex-row items-center justify-between px-4 py-3 bg-surface-dark/50 border border-white/10 rounded-2xl">
                            <View className="flex-row items-center gap-2">
                                <MaterialIcons name="directions-car" size={18} color="#60a5fa" />
                                <Text className="text-white text-[13px] font-bold">{selectedVehicleName}</Text>
                            </View>
                            <TouchableOpacity
                                onPress={() => setVehicleSelectVisible(true)}
                                className="bg-primary/20 px-3 py-1.5 rounded-lg border border-primary/30 active:bg-primary/30"
                            >
                                <Text className="text-primary-light text-[11px] font-bold">차량 변경</Text>
                            </TouchableOpacity>
                        </View>
                    )}
                </View>

                <ScrollView
                    ref={scrollRef}
                    className="flex-1 px-5"
                    contentContainerStyle={{ paddingBottom: 20 }}
                    onContentSizeChange={() => scrollToEnd()}
                    onLayout={() => scrollToEnd()}
                    showsVerticalScrollIndicator={false}
                >
                    {messages.map((msg, idx) => (
                        <View key={msg.id} className={`flex-row items-start gap-3 max-w-[88%] ${idx > 0 ? 'mt-4' : 'mb-2'}`}>
                            {msg.type === 'ai' && (
                                <View className="mt-1">
                                    <View className="w-9 h-9 rounded-xl bg-surface-dark border border-white/20 items-center justify-center shadow-sm">
                                        <MaterialIcons name="analytics" size={20} color="#3d7eff" />
                                    </View>
                                </View>
                            )}
                            <View className="gap-1.5 shrink">
                                {msg.type === 'ai' && <Text className="text-text-muted text-[11px] font-bold ml-1 tracking-tight">AI DIAGNOSTICS</Text>}
                                <View className={`bg-surface-dark border border-white/10 rounded-2xl ${msg.type === 'ai' ? 'rounded-tl-none' : 'rounded-tr-none'} px-4 py-3.5 shadow-sm`}>
                                    <Text className="text-[15px] text-white/95 leading-relaxed">{msg.text}</Text>
                                </View>
                            </View>
                        </View>
                    ))}

                    <View className="flex-row items-start gap-3 max-w-[88%] mt-4">
                        <View className="w-9 h-9" />
                        <View className="gap-1.5 shrink -mt-2">
                            <View className="bg-surface-dark border border-white/10 border-l-2 border-l-primary rounded-2xl rounded-tl-none px-4 py-3.5 shadow-sm">
                                <Text className="text-[15px] text-white/95 font-medium leading-relaxed">
                                    정확한 진단을 위해 몇 가지 데이터가 필요합니다. 먼저 <Text className="text-primary-light font-bold">엔진 시동음</Text>을 녹음할까요?
                                </Text>
                            </View>
                        </View>
                    </View>
                </ScrollView>
            </View>

            <VehicleSelectModal
                visible={vehicleSelectVisible}
                onClose={() => {
                    if (!selectedVehicleId && !isConnected && !selectionRef.current) {
                        navigation.goBack();
                    } else {
                        setVehicleSelectVisible(false);
                    }
                }}
                onSelect={handleVehicleSelect}
                description="진단을 진행할 차량을 선택해주세요."
            />
        </BaseScreen>
    );
}
