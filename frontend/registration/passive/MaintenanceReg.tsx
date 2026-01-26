import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Modal, TextInput, Pressable, FlatList, KeyboardAvoidingView, Platform, Keyboard, ActivityIndicator } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { StatusBar } from 'expo-status-bar';
import { format } from 'date-fns';
import { useRegistrationStore } from '../../store/useRegistrationStore';
import { useAlertStore } from '../../store/useAlertStore';
import { useDatePickerStore } from '../../store/useDatePickerStore';
import { ConsumableMaster } from '../../api/masterApi';

export default function MaintenanceReg() {
    const navigation = useNavigation<any>();
    const insets = useSafeAreaInsets();
    const store = useRegistrationStore();
    const datePickerStore = useDatePickerStore(); // Use global picker

    // UI State
    const [modalVisible, setModalVisible] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    // const [datePickerVisible, setDatePickerVisible] = useState(false); // Removed
    // const [selectedItemCode, setSelectedItemCode] = useState<string | null>(null); // Removed

    useEffect(() => {
        const init = async () => {
            await store.loadConsumableMaster();
            store.addDefaultConsumables();
        };
        init();
    }, []);

    // Helper: Handle Registration
    const handleComplete = async () => {
        const result = await store.registerAll();
        if (result.success) {
            useAlertStore.getState().showAlert('등록 완료', '차량과 정비 이력이 성공적으로 등록되었습니다.', 'SUCCESS', () => {
                navigation.navigate('MainPage'); // Or reset stack
            });
        } else {
            useAlertStore.getState().showAlert('오류', result.message || '등록 중 문제가 발생했습니다.', 'ERROR');
        }
    };

    // Helper: Filter Master List
    const filteredMasterList = store.consumableMasterList.filter(item => {
        const query = searchQuery.toLowerCase();
        return item.name.toLowerCase().includes(query) || item.category.toLowerCase().includes(query);
    });

    // Helper: Date Picker
    const showDatePicker = (itemCode: string) => {
        datePickerStore.openDatePicker({
            mode: 'date',
            initialDate: new Date(),
            onConfirm: (date) => {
                store.updateMaintenanceRecord(itemCode, 'date', format(date, 'yyyy-MM-dd'));
            }
        });
    };

    // Render Consumable Item Card (Input Form)
    const renderRecordCard = (item: typeof store.maintenanceRecords[0]) => {
        return (
            <View key={item.itemCode} className="bg-surface-card border border-white/10 rounded-xl p-4 mb-4">
                <View className="flex-row justify-between items-center mb-4">
                    <View className="flex-row items-center gap-3">
                        <Text className="text-white font-bold text-base">{item.itemName}</Text>
                    </View>
                    <TouchableOpacity onPress={() => store.removeMaintenanceRecord(item.itemCode)}>
                        <MaterialIcons name="close" size={20} color="#94a3b8" />
                    </TouchableOpacity>
                </View>

                <View className="flex-row gap-3">
                    {/* Date Input */}
                    <TouchableOpacity
                        className="flex-1"
                        onPress={() => showDatePicker(item.itemCode)}
                    >
                        <Text className="text-xs text-text-dim mb-1 ml-1">마지막 교체일</Text>
                        <View className="h-12 bg-black/30 border border-white/10 rounded-lg flex-row items-center px-3">
                            <MaterialIcons name="event" size={18} color="#94a3b8" />
                            <Text className={`ml-2 text-sm ${item.lastReplacementDate ? 'text-white' : 'text-slate-500'}`}>
                                {item.lastReplacementDate || '날짜 선택'}
                            </Text>
                        </View>
                    </TouchableOpacity>

                    {/* Mileage Input */}
                    <View className="flex-1">
                        <Text className="text-xs text-text-dim mb-1 ml-1">교체 시점 주행거리</Text>
                        <View className="h-12 bg-black/30 border border-white/10 rounded-lg flex-row items-center px-3">
                            <MaterialIcons name="speed" size={18} color="#94a3b8" />
                            <TextInput
                                value={item.lastReplacementMileage}
                                onChangeText={(t) => store.updateMaintenanceRecord(item.itemCode, 'mileage', t.replace(/[^0-9]/g, ''))}
                                placeholder="0"
                                placeholderTextColor="#64748b"
                                keyboardType="number-pad"
                                className="flex-1 ml-2 text-white text-sm h-full"
                            />
                            <Text className="text-xs text-slate-500">km</Text>
                        </View>
                    </View>
                </View>
            </View>
        );
    };

    return (
        <View className="flex-1 bg-background-dark">
            <StatusBar style="light" />

            {/* Header */}
            <View className="bg-background-dark/80 backdrop-blur-md z-50 sticky top-0" style={{ paddingTop: insets.top }}>
                <View className="flex-row items-center justify-between px-4 py-3 pb-4">
                    <TouchableOpacity
                        className="w-10 h-10 items-center justify-center rounded-full hover:bg-white/10"
                        onPress={() => navigation.goBack()}
                    >
                        <MaterialIcons name="arrow-back-ios-new" size={24} color="white" />
                    </TouchableOpacity>
                    <Text className="text-white text-lg font-bold tracking-tight text-center flex-1 pr-10">
                        소모품 교체 이력
                    </Text>
                </View>
            </View>

            <ScrollView className="flex-1 px-5" contentContainerStyle={{ paddingBottom: 120 }}>
                <View className="mt-2 mb-6">
                    <Text className="text-white text-xl font-bold mb-2">
                        최근 정비한 내역이 있나요?
                    </Text>
                    <Text className="text-slate-400 text-sm leading-relaxed">
                        AI가 다음 교체 시기를 예측해드립니다.
                    </Text>
                    <Text className="text-primary/80 text-xs mt-3 font-medium">
                        * 날짜 또는 주행거리 중 하나만 입력해도 됩니다.
                    </Text>
                </View>

                {/* List of Added Records */}
                {store.maintenanceRecords.map(item => renderRecordCard(item))}

                {/* Add Button */}
                <TouchableOpacity
                    onPress={() => setModalVisible(true)}
                    className="w-full py-4 border border-dashed border-white/20 rounded-xl items-center justify-center flex-row gap-2 active:bg-white/5 mb-8"
                >
                    <MaterialIcons name="add-circle-outline" size={24} color="#0d7ff2" />
                    <Text className="text-primary font-bold">소모품 추가하기</Text>
                </TouchableOpacity>

            </ScrollView>

            {/* Bottom Actions */}
            <View className="absolute bottom-0 left-0 right-0 p-5 bg-gradient-to-t from-[#0B0C10] via-[#0B0C10] to-transparent" style={{ paddingBottom: insets.bottom + 10 }}>
                <TouchableOpacity
                    onPress={handleComplete}
                    className="w-full h-14 bg-primary rounded-xl shadow-lg shadow-blue-500/30 flex-row items-center justify-center gap-2 active:opacity-90 mb-3"
                >
                    <Text className="text-white font-bold text-lg">등록</Text>
                    <MaterialIcons name="check" size={20} color="white" />
                </TouchableOpacity>

                <TouchableOpacity
                    onPress={() => {
                        store.clearMaintenanceRecords();
                        handleComplete();
                    }}
                    className="w-full h-12 flex-row items-center justify-center"
                >
                    <Text className="text-slate-400 font-medium text-base underline">
                        다음에 입력하기 (건너뛰기)
                    </Text>
                </TouchableOpacity>
            </View>

            {/* Selection Modal */}
            <Modal
                visible={modalVisible}
                transparent={true}
                animationType="slide"
                onRequestClose={() => setModalVisible(false)}
            >
                <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} className="flex-1">
                    <Pressable className="flex-1 bg-black/60 justify-end" onPress={() => setModalVisible(false)}>
                        <Pressable className="bg-surface-dark rounded-t-3xl h-[70%]" onPress={(e) => e.stopPropagation()}>
                            <View className="flex-row items-center justify-between p-4 border-b border-border-dark">
                                <Text className="text-lg font-bold text-white">소모품 선택</Text>
                                <TouchableOpacity onPress={() => setModalVisible(false)}>
                                    <MaterialIcons name="close" size={24} color="#94a3b8" />
                                </TouchableOpacity>
                            </View>

                            <View className="px-4 py-3">
                                <View className="bg-background-dark border border-border-dark rounded-xl px-3 h-12 flex-row items-center">
                                    <MaterialIcons name="search" size={20} color="#94a3b8" />
                                    <TextInput
                                        value={searchQuery}
                                        onChangeText={setSearchQuery}
                                        placeholder="소모품 이름 검색"
                                        placeholderTextColor="#64748b"
                                        className="flex-1 ml-2 text-white text-base"
                                    />
                                </View>
                            </View>

                            <FlatList
                                data={filteredMasterList}
                                keyExtractor={(item) => item.code}
                                renderItem={({ item }) => (
                                    <TouchableOpacity
                                        className="flex-row items-center gap-4 p-4 border-b border-white/5 active:bg-white/5"
                                        onPress={() => {
                                            store.addMaintenanceRecord(item);
                                            setModalVisible(false);
                                        }}
                                    >
                                        <View>
                                            <Text className="text-white font-medium">{item.name}</Text>
                                            <Text className="text-text-dim text-xs mt-0.5">교체 주기: {item.replacementCycleKm?.toLocaleString()}km</Text>
                                        </View>
                                    </TouchableOpacity>
                                )}
                            />
                        </Pressable>
                    </Pressable>
                </KeyboardAvoidingView>
            </Modal>

            {/* Date Picker Helper -> Removed (Global Used) */}

            {/* Loading Overlay */}
            {store.isLoading && (
                <View className="absolute inset-0 bg-black/50 items-center justify-center z-[100]">
                    <View className="bg-surface-dark p-6 rounded-2xl items-center">
                        <ActivityIndicator size="large" color="#0d7ff2" />
                        <Text className="text-white mt-4 font-bold">등록 중입니다...</Text>
                    </View>
                </View>
            )}
        </View>
    );
}
