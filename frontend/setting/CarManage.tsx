import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Modal, Pressable } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';

// 차량 데이터 타입
export interface Vehicle {
    id: string;
    name: string;
    plate: string;
    mileage: string;
    fuel: string;
}

// 샘플 차량 목록
export const vehicleList: Vehicle[] = [
    { id: '1', name: 'Genesis GV80', plate: '12가 3456', mileage: '24,580 km', fuel: '68%' },
    { id: '2', name: 'Hyundai Ioniq 6', plate: '34나 7890', mileage: '15,230 km', fuel: '82%' },
    { id: '3', name: 'Kia EV9', plate: '56다 1234', mileage: '8,150 km', fuel: '45%' },
];

// AsyncStorage 키
const PRIMARY_VEHICLE_KEY = 'primaryVehicle';

export default function CarManage() {
    const navigation = useNavigation<any>();
    const [selectedVehicle, setSelectedVehicle] = useState<Vehicle>(vehicleList[0]);
    const [modalVisible, setModalVisible] = useState(false);

    // 저장된 대표 차량 불러오기
    useEffect(() => {
        const loadPrimaryVehicle = async () => {
            try {
                const stored = await AsyncStorage.getItem(PRIMARY_VEHICLE_KEY);
                if (stored) {
                    const vehicle = JSON.parse(stored) as Vehicle;
                    setSelectedVehicle(vehicle);
                }
            } catch (e) {
                console.error('대표 차량 불러오기 실패:', e);
            }
        };
        loadPrimaryVehicle();
    }, []);

    // 대표 차량 선택 핸들러
    const handleSelectPrimaryVehicle = async (vehicle: Vehicle) => {
        try {
            await AsyncStorage.setItem(PRIMARY_VEHICLE_KEY, JSON.stringify(vehicle));
            setSelectedVehicle(vehicle);
            setModalVisible(false);
        } catch (e) {
            console.error('대표 차량 저장 실패:', e);
        }
    };

    return (
        <View className="flex-1 bg-[#050505]">
            <StatusBar style="light" />
            <SafeAreaView className="flex-1" edges={['top']}>

                {/* Header */}
                <View className="flex-row items-center px-4 py-3 border-b border-white/5 bg-[#050505]/80">
                    <TouchableOpacity
                        className="w-10 h-10 items-center justify-center -ml-2 rounded-full hover:bg-white/5 active:bg-white/10"
                        onPress={() => navigation.goBack()}
                    >
                        <MaterialIcons name="arrow-back-ios-new" size={24} color="#f1f5f9" />
                    </TouchableOpacity>
                    <Text className="text-xl font-bold text-slate-100 flex-1 ml-2">내 차량 관리</Text>
                    <View className="w-10" />
                </View>

                <ScrollView className="flex-1 px-5 pt-6" contentContainerStyle={{ paddingBottom: 50 }}>

                    {/* Main Car Card */}
                    <View className="relative overflow-hidden rounded-3xl border border-white/10 mb-8">
                        <LinearGradient
                            colors={['rgba(26, 30, 35, 0.6)', 'rgba(26, 30, 35, 0.9)']}
                            className="p-6"
                        >
                            {/* Glow Effect */}
                            <View className="absolute top-0 right-0 w-32 h-32 bg-primary/20 blur-3xl rounded-full translate-x-10 -translate-y-10 pointer-events-none" />

                            <View className="flex-row justify-between items-start mb-6">
                                <View>
                                    <View className="flex-row items-center gap-1.5 px-3 py-1 bg-primary/20 border border-primary/30 rounded-full mb-3 self-start">
                                        <View className="w-1.5 h-1.5 bg-primary rounded-full" />
                                        <Text className="text-[10px] font-bold text-primary uppercase tracking-wider">대표 차량</Text>
                                    </View>
                                    <Text className="text-2xl font-bold text-white tracking-tight mb-1">{selectedVehicle.name}</Text>
                                    <Text className="text-slate-400 text-sm">{selectedVehicle.plate}</Text>
                                </View>
                                <View className="bg-white/5 p-2 rounded-xl border border-white/5">
                                    <MaterialIcons name="verified-user" size={24} color="#0d7ff2" />
                                </View>
                            </View>

                            <View className="flex-row gap-3 mt-2">
                                <View className="flex-1 bg-white/5 border border-white/10 rounded-2xl p-4 backdrop-blur-md">
                                    <Text className="text-[10px] text-slate-500 mb-1">총 주행거리</Text>
                                    <Text className="text-base font-bold text-slate-100">{selectedVehicle.mileage}</Text>
                                </View>
                                <View className="flex-1 bg-white/5 border border-white/10 rounded-2xl p-4 backdrop-blur-md">
                                    <Text className="text-[10px] text-slate-500 mb-1">잔여 연료</Text>
                                    <Text className="text-base font-bold text-slate-100">{selectedVehicle.fuel}</Text>
                                </View>
                            </View>
                        </LinearGradient>
                    </View>

                    {/* Management Menu */}
                    <Text className="px-2 text-[13px] font-semibold text-slate-500 uppercase tracking-widest mb-3">관리 메뉴</Text>
                    <View className="bg-[#1a1e23]/60 border border-white/5 rounded-2xl overflow-hidden mb-6 backdrop-blur-md">
                        <TouchableOpacity
                            className="flex-row items-center gap-4 px-5 py-4 active:bg-white/5 border-b border-white/5"
                            onPress={() => navigation.navigate('Spec')}
                        >
                            <View className="w-11 h-11 items-center justify-center rounded-xl bg-slate-800 shrink-0">
                                <MaterialIcons name="list-alt" size={24} color="#cbd5e1" />
                            </View>
                            <Text className="text-slate-100 text-base font-medium flex-1">차량 상세 제원 보기</Text>
                            <MaterialIcons name="chevron-right" size={24} color="#475569" />
                        </TouchableOpacity>

                        <TouchableOpacity
                            className="flex-row items-center gap-4 px-5 py-4 active:bg-white/5 border-b border-white/5"
                            onPress={() => setModalVisible(true)}
                        >
                            <View className="w-11 h-11 items-center justify-center rounded-xl bg-slate-800 shrink-0">
                                <MaterialIcons name="star-half" size={24} color="#cbd5e1" />
                            </View>
                            <Text className="text-slate-100 text-base font-medium flex-1">대표 차량으로 설정</Text>
                            <MaterialIcons name="chevron-right" size={24} color="#475569" />
                        </TouchableOpacity>

                        <TouchableOpacity className="flex-row items-center gap-4 px-5 py-4 active:bg-white/5">
                            <View className="w-11 h-11 items-center justify-center rounded-xl bg-slate-800 shrink-0">
                                <MaterialIcons name="edit" size={24} color="#cbd5e1" />
                            </View>
                            <Text className="text-slate-100 text-base font-medium flex-1">차량 정보 수정</Text>
                            <MaterialIcons name="chevron-right" size={24} color="#475569" />
                        </TouchableOpacity>
                    </View>

                    {/* Register Button */}
                    <TouchableOpacity
                        className="w-full py-4 bg-primary/10 rounded-2xl flex-row items-center justify-center gap-2 border border-primary/30 active:bg-primary/20"
                        activeOpacity={0.8}
                    >
                        <MaterialIcons name="add-circle-outline" size={24} color="#0d7ff2" />
                        <Text className="text-primary font-bold text-base">새 차량 등록하기</Text>
                    </TouchableOpacity>

                </ScrollView>
            </SafeAreaView>

            {/* 대표 차량 선택 모달 */}
            <Modal
                animationType="fade"
                transparent={true}
                visible={modalVisible}
                onRequestClose={() => setModalVisible(false)}
            >
                <Pressable
                    className="flex-1 bg-black/70 justify-center items-center px-6"
                    onPress={() => setModalVisible(false)}
                >
                    <Pressable
                        className="w-full bg-[#1a1e23] border border-white/10 rounded-3xl overflow-hidden"
                        onPress={(e) => e.stopPropagation()}
                    >
                        {/* 모달 헤더 */}
                        <View className="px-6 py-5 border-b border-white/10 flex-row items-center justify-between">
                            <Text className="text-lg font-bold text-white">대표 차량 선택</Text>
                            <TouchableOpacity
                                className="w-8 h-8 items-center justify-center rounded-full bg-white/5 active:bg-white/10"
                                onPress={() => setModalVisible(false)}
                            >
                                <MaterialIcons name="close" size={20} color="#94a3b8" />
                            </TouchableOpacity>
                        </View>

                        {/* 차량 목록 */}
                        <ScrollView className="max-h-80">
                            {vehicleList.map((vehicle, index) => {
                                const isSelected = selectedVehicle.id === vehicle.id;
                                const isLast = index === vehicleList.length - 1;

                                return (
                                    <TouchableOpacity
                                        key={vehicle.id}
                                        className={`flex-row items-center gap-4 px-6 py-4 active:bg-white/5 ${!isLast ? 'border-b border-white/5' : ''
                                            } ${isSelected ? 'bg-primary/10' : ''}`}
                                        onPress={() => handleSelectPrimaryVehicle(vehicle)}
                                    >
                                        {/* 차량 아이콘 */}
                                        <View className={`w-12 h-12 items-center justify-center rounded-xl ${isSelected ? 'bg-primary/20 border border-primary/30' : 'bg-white/5 border border-white/10'
                                            }`}>
                                            <MaterialIcons
                                                name="directions-car"
                                                size={24}
                                                color={isSelected ? '#0d7ff2' : '#94a3b8'}
                                            />
                                        </View>

                                        {/* 차량 정보 */}
                                        <View className="flex-1">
                                            <Text className={`text-base font-semibold mb-0.5 ${isSelected ? 'text-primary' : 'text-white'}`}>
                                                {vehicle.name}
                                            </Text>
                                            <Text className="text-slate-500 text-xs">{vehicle.plate}</Text>
                                        </View>

                                        {/* 선택 표시 */}
                                        {isSelected ? (
                                            <View className="w-6 h-6 items-center justify-center rounded-full bg-primary">
                                                <MaterialIcons name="check" size={16} color="#fff" />
                                            </View>
                                        ) : (
                                            <View className="w-6 h-6 rounded-full border-2 border-white/20" />
                                        )}
                                    </TouchableOpacity>
                                );
                            })}
                        </ScrollView>

                        {/* 모달 푸터 */}
                        <View className="px-6 py-4 border-t border-white/10">
                            <Text className="text-xs text-slate-500 text-center">
                                대표 차량으로 설정하면 메인 화면에 해당 차량 정보가 표시됩니다.
                            </Text>
                        </View>
                    </Pressable>
                </Pressable>
            </Modal>
        </View>
    );
}
