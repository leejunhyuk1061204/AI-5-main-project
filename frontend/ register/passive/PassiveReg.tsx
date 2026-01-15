import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ScrollView, Modal, FlatList, Pressable } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { StatusBar } from 'expo-status-bar';

// Vehicle Options
const VEHICLE_MAKES = [
    { label: '현대 (Hyundai)', value: 'hyundai' },
    { label: '기아 (Kia)', value: 'kia' },
    { label: '제네시스 (Genesis)', value: 'genesis' },
    { label: 'BMW', value: 'bmw' },
    { label: 'Mercedes-Benz', value: 'mercedes' },
    { label: 'Audi', value: 'audi' },
    { label: 'Tesla', value: 'tesla' },
];

export default function PassiveReg() {
    const navigation = useNavigation();
    const insets = useSafeAreaInsets();

    // Form State
    const [vehicleNumber, setVehicleNumber] = useState('');
    const [vin, setVin] = useState('');
    const [selectedMake, setSelectedMake] = useState<{ label: string; value: string } | null>(null);
    const [fuelType, setFuelType] = useState('gasoline');
    const [isMakeModalVisible, setMakeModalVisible] = useState(false);

    // Helper to render Fuel Option
    const FuelOption = ({ type, label, icon, value }: { type: string, label: string, icon: keyof typeof MaterialIcons.glyphMap, value: string }) => (
        <Pressable
            onPress={() => setFuelType(value)}
            className={`flex-1 flex-col items-center justify-center h-20 rounded-xl border transition-all duration-200 ${fuelType === value
                ? 'border-primary bg-primary/10'
                : 'border-border-dark bg-[#15181E]'
                }`}
        >
            <MaterialIcons
                name={icon}
                size={24}
                color={fuelType === value ? '#0d7ff2' : '#94a3b8'}
                style={{ marginBottom: 4 }}
            />
            <Text className={`text-sm font-medium ${fuelType === value ? 'text-primary' : 'text-slate-400'
                }`}>
                {label}
            </Text>
        </Pressable>
    );

    return (
        <View className="flex-1 bg-[#0B0C10]">
            <StatusBar style="light" />

            {/* Header */}
            <View
                className="bg-[#0B0C10]/80 backdrop-blur-md z-50 sticky top-0"
                style={{ paddingTop: insets.top }}
            >
                <View className="flex-row items-center justify-between px-4 py-3 pb-4">
                    <TouchableOpacity
                        className="w-10 h-10 items-center justify-center rounded-full hover:bg-white/10"
                        onPress={() => navigation.goBack()}
                    >
                        <MaterialIcons name="arrow-back-ios-new" size={24} color="white" />
                    </TouchableOpacity>
                    <Text className="text-white text-lg font-bold tracking-tight text-center flex-1 pr-10">
                        새 차량 등록
                    </Text>
                </View>
            </View>

            {/* Main Content */}
            <ScrollView
                className="flex-1 px-5"
                contentContainerStyle={{ paddingBottom: 120 }}
                showsVerticalScrollIndicator={false}
            >
                <View className="space-y-8 mt-2">

                    {/* Vehicle Number */}
                    <View>
                        <Text className="text-sm font-medium text-slate-400 mb-2 pl-1">차량 번호</Text>
                        <TextInput
                            value={vehicleNumber}
                            onChangeText={setVehicleNumber}
                            placeholder="예: 12가 3456"
                            placeholderTextColor="#94a3b8"
                            className="w-full h-14 bg-[#15181E] border border-border-dark rounded-xl px-4 text-base text-white focus:border-primary"
                        />
                    </View>

                    {/* VIN Number */}
                    <View>
                        <Text className="text-sm font-medium text-slate-400 mb-2 pl-1">차대번호 (VIN)</Text>
                        <View className="relative flex-row items-center">
                            <TextInput
                                value={vin}
                                onChangeText={setVin}
                                placeholder="17자리 영문+숫자"
                                placeholderTextColor="#94a3b8"
                                className="w-full h-14 bg-[#15181E] border border-border-dark rounded-xl pl-4 pr-14 text-base text-white focus:border-primary uppercase"
                            />
                            <TouchableOpacity className="absolute right-2 p-2">
                                <MaterialIcons name="center-focus-strong" size={24} color="#0d7ff2" />
                            </TouchableOpacity>
                        </View>
                        <Text className="text-xs text-slate-500 mt-2 pl-1">
                            등록증 하단의 차대번호를 입력하거나 스캔하세요.
                        </Text>
                    </View>

                    {/* Manufacturer / Model - Custom Dropdown Trigger */}
                    <View>
                        <Text className="text-sm font-medium text-slate-400 mb-2 pl-1">제조사 / 모델</Text>
                        <TouchableOpacity
                            onPress={() => setMakeModalVisible(true)}
                            className="relative w-full h-14 bg-[#15181E] border border-border-dark rounded-xl px-4 justify-center"
                        >
                            <Text className={`text-base ${selectedMake ? 'text-white' : 'text-slate-400'}`}>
                                {selectedMake ? selectedMake.label : '차량을 선택해주세요'}
                            </Text>
                            <View className="absolute right-4">
                                <MaterialIcons name="expand-more" size={24} color="#94a3b8" />
                            </View>
                        </TouchableOpacity>
                    </View>

                    {/* Fuel Type */}
                    <View>
                        <Text className="text-sm font-medium text-slate-400 mb-3 pl-1">연료 타입</Text>
                        <View className="flex-row gap-3">
                            <View className="flex-1 gap-3">
                                <FuelOption type="radio" value="gasoline" label="가솔린" icon="local-gas-station" />
                                <FuelOption type="radio" value="electric" label="전기차" icon="electric-bolt" />
                            </View>
                            <View className="flex-1 gap-3">
                                <FuelOption type="radio" value="diesel" label="디젤" icon="oil-barrel" />
                                <FuelOption type="radio" value="hybrid" label="하이브리드" icon="battery-charging-full" />
                            </View>
                        </View>
                    </View>

                </View>
            </ScrollView>

            {/* Bottom Action Bar */}
            <View
                className="absolute bottom-0 left-0 right-0 p-5 bg-gradient-to-t from-[#0B0C10] via-[#0B0C10] to-transparent"
                style={{ paddingBottom: insets.bottom + 10 }}
            >
                <TouchableOpacity
                    className="w-full h-14 bg-primary rounded-xl shadow-lg shadow-blue-500/30 flex-row items-center justify-center gap-2 active:opacity-90"
                    activeOpacity={0.8}
                >
                    <Text className="text-white font-bold text-lg">등록 완료</Text>
                    <MaterialIcons name="arrow-forward" size={20} color="white" />
                </TouchableOpacity>
            </View>

            {/* Make Selection Modal */}
            <Modal
                visible={isMakeModalVisible}
                transparent={true}
                animationType="fade"
                onRequestClose={() => setMakeModalVisible(false)}
            >
                <TouchableOpacity
                    activeOpacity={1}
                    onPress={() => setMakeModalVisible(false)}
                    className="flex-1 bg-black/60 justify-end"
                >
                    <View className="bg-white dark:bg-[#15181E] rounded-t-3xl overflow-hidden pb-10">
                        <View className="flex-row items-center justify-between p-4 border-b border-slate-200 dark:border-border-dark">
                            <Text className="text-lg font-bold text-slate-900 dark:text-white">제조사 선택</Text>
                            <TouchableOpacity onPress={() => setMakeModalVisible(false)}>
                                <MaterialIcons name="close" size={24} color="#94a3b8" />
                            </TouchableOpacity>
                        </View>
                        <FlatList
                            data={VEHICLE_MAKES}
                            keyExtractor={(item) => item.value}
                            renderItem={({ item }) => (
                                <TouchableOpacity
                                    className="p-4 border-b border-slate-100 dark:border-slate-800"
                                    onPress={() => {
                                        setSelectedMake(item);
                                        setMakeModalVisible(false);
                                    }}
                                >
                                    <Text className="text-base text-slate-700 dark:text-slate-200">{item.label}</Text>
                                </TouchableOpacity>
                            )}
                        />
                    </View>
                </TouchableOpacity>
            </Modal>

        </View>
    );
}
