import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Image, TextInput, ActivityIndicator, KeyboardAvoidingView, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons } from '@expo/vector-icons';
import { useAlertStore } from '../store/useAlertStore';
import ocrApi, { OcrAnalysisResponse } from '../api/ocrApi';

// 소모품 항목 목록
const CONSUMABLE_ITEMS = [
    { code: 'ENGINE_OIL', name: '엔진 오일' },
    { code: 'TIRE_FRONT', name: '앞 타이어' },
    { code: 'TIRE_REAR', name: '뒤 타이어' },
    { code: 'BRAKE_PAD_FRONT', name: '앞 브레이크 패드' },
    { code: 'BRAKE_PAD_REAR', name: '뒤 브레이크 패드' },
    { code: 'BATTERY_12V', name: '12V 배터리' },
    { code: 'CABIN_FILTER', name: '에어컨 필터' },
    { code: 'COOLANT', name: '냉각수' },
    { code: 'OTHER', name: '기타' },
];

export default function ReceiptResult({ navigation, route }: { navigation?: any; route?: any }) {
    const { vehicleId, imageUri, ocrResult } = route?.params || {};
    const result: OcrAnalysisResponse = ocrResult || {};

    // 편집 가능한 상태
    const [shopName, setShopName] = useState(result.shopName || '');
    const [maintenanceDate, setMaintenanceDate] = useState(result.maintenanceDate || '');
    const [cost, setCost] = useState(result.cost?.toString() || '');
    const [mileage, setMileage] = useState(result.mileageAtMaintenance?.toString() || '');
    const [selectedItem, setSelectedItem] = useState(result.consumableItemCode || 'OTHER');
    const [memo, setMemo] = useState('');
    const [isSaving, setIsSaving] = useState(false);
    const [showItemPicker, setShowItemPicker] = useState(false);

    // 저장 처리
    const handleSave = async () => {
        if (!vehicleId) {
            useAlertStore.getState().showAlert('오류', '차량 정보가 없습니다.', 'ERROR');
            return;
        }

        setIsSaving(true);
        try {
            // FormData 생성
            const formData = new FormData();
            formData.append('file', {
                uri: imageUri,
                type: 'image/jpeg',
                name: 'receipt.jpg',
            } as any);

            // API 호출 (analyze-save)
            await ocrApi.analyzeAndSaveReceipt(vehicleId, formData);

            useAlertStore.getState().showAlert(
                '저장 완료',
                '정비 이력이 저장되었습니다.',
                'SUCCESS',
                () => {
                    // 차계부 메인으로 돌아가기
                    navigation.navigate('MaintenanceBook');
                }
            );
        } catch (error: any) {
            console.error('Save Error:', error);
            useAlertStore.getState().showAlert(
                '저장 실패',
                error.message || '저장 중 오류가 발생했습니다.',
                'ERROR'
            );
        } finally {
            setIsSaving(false);
        }
    };

    // 재촬영
    const handleRetake = () => {
        navigation.goBack();
    };

    // 선택된 항목 이름 찾기
    const getSelectedItemName = () => {
        const item = CONSUMABLE_ITEMS.find(i => i.code === selectedItem);
        return item?.name || '선택하세요';
    };

    return (
        <SafeAreaView className="flex-1 bg-background-dark">
            <StatusBar style="light" />

            {/* Header */}
            <View className="flex-row items-center justify-between px-4 py-3 border-b border-white/5">
                <TouchableOpacity
                    onPress={handleRetake}
                    className="w-10 h-10 items-center justify-center rounded-full active:bg-white/10"
                >
                    <MaterialIcons name="arrow-back-ios" size={20} color="white" />
                </TouchableOpacity>

                <Text className="text-white text-lg font-bold">분석 결과</Text>

                <View className="w-10" />
            </View>

            <KeyboardAvoidingView
                behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
                className="flex-1"
            >
                <ScrollView className="flex-1" contentContainerStyle={{ paddingBottom: 120 }}>
                    {/* 원본 이미지 */}
                    <View className="px-5 pt-4">
                        <Text className="text-[13px] font-semibold text-text-dim uppercase tracking-widest mb-3">
                            원본 영수증
                        </Text>
                        <View className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden">
                            <Image
                                source={{ uri: imageUri }}
                                className="w-full h-48"
                                resizeMode="contain"
                            />
                        </View>
                    </View>

                    {/* 추출된 데이터 */}
                    <View className="px-5 pt-6">
                        <Text className="text-[13px] font-semibold text-text-dim uppercase tracking-widest mb-3">
                            추출된 정보
                        </Text>

                        <View className="bg-white/5 border border-white/10 rounded-2xl p-4 gap-4">
                            {/* 정비소 */}
                            <View>
                                <Text className="text-text-dim text-xs mb-2">정비소</Text>
                                <TextInput
                                    className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white"
                                    value={shopName}
                                    onChangeText={setShopName}
                                    placeholder="정비소 이름"
                                    placeholderTextColor="#64748b"
                                />
                            </View>

                            {/* 정비일 */}
                            <View>
                                <Text className="text-text-dim text-xs mb-2">정비일</Text>
                                <TextInput
                                    className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white"
                                    value={maintenanceDate}
                                    onChangeText={setMaintenanceDate}
                                    placeholder="YYYY-MM-DD"
                                    placeholderTextColor="#64748b"
                                />
                            </View>

                            {/* 비용 */}
                            <View>
                                <Text className="text-text-dim text-xs mb-2">비용</Text>
                                <TextInput
                                    className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white"
                                    value={cost}
                                    onChangeText={setCost}
                                    placeholder="정비 비용"
                                    placeholderTextColor="#64748b"
                                    keyboardType="numeric"
                                />
                            </View>

                            {/* 주행거리 */}
                            <View>
                                <Text className="text-text-dim text-xs mb-2">주행거리 (km)</Text>
                                <TextInput
                                    className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white"
                                    value={mileage}
                                    onChangeText={setMileage}
                                    placeholder="주행거리"
                                    placeholderTextColor="#64748b"
                                    keyboardType="numeric"
                                />
                            </View>

                            {/* 정비 항목 */}
                            <View>
                                <Text className="text-text-dim text-xs mb-2">정비 항목</Text>
                                <TouchableOpacity
                                    className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 flex-row justify-between items-center"
                                    onPress={() => setShowItemPicker(!showItemPicker)}
                                >
                                    <Text className="text-white">{getSelectedItemName()}</Text>
                                    <MaterialIcons name="arrow-drop-down" size={24} color="#94a3b8" />
                                </TouchableOpacity>

                                {showItemPicker && (
                                    <View className="bg-surface-dark border border-white/10 rounded-xl mt-2 overflow-hidden">
                                        {CONSUMABLE_ITEMS.map((item) => (
                                            <TouchableOpacity
                                                key={item.code}
                                                className={`px-4 py-3 border-b border-white/5 ${selectedItem === item.code ? 'bg-primary/20' : ''}`}
                                                onPress={() => {
                                                    setSelectedItem(item.code);
                                                    setShowItemPicker(false);
                                                }}
                                            >
                                                <Text className={`${selectedItem === item.code ? 'text-primary font-bold' : 'text-white'}`}>
                                                    {item.name}
                                                </Text>
                                            </TouchableOpacity>
                                        ))}
                                    </View>
                                )}
                            </View>

                            {/* 메모 */}
                            <View>
                                <Text className="text-text-dim text-xs mb-2">메모 (선택)</Text>
                                <TextInput
                                    className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white"
                                    value={memo}
                                    onChangeText={setMemo}
                                    placeholder="추가 메모"
                                    placeholderTextColor="#64748b"
                                    multiline
                                    numberOfLines={3}
                                    textAlignVertical="top"
                                />
                            </View>
                        </View>
                    </View>
                </ScrollView>
            </KeyboardAvoidingView>

            {/* Bottom Buttons */}
            <View className="absolute bottom-0 left-0 right-0 bg-background-dark border-t border-white/5 px-5 py-4 pb-8">
                <View className="flex-row gap-3">
                    <TouchableOpacity
                        className="flex-1 bg-[#1e2936] py-4 rounded-xl items-center"
                        onPress={handleRetake}
                        disabled={isSaving}
                    >
                        <Text className="text-white font-bold">재촬영</Text>
                    </TouchableOpacity>

                    <TouchableOpacity
                        className="flex-[2] bg-primary py-4 rounded-xl items-center flex-row justify-center gap-2"
                        onPress={handleSave}
                        disabled={isSaving}
                    >
                        {isSaving ? (
                            <ActivityIndicator color="white" size="small" />
                        ) : (
                            <>
                                <MaterialIcons name="save" size={20} color="white" />
                                <Text className="text-white font-bold text-base">저장</Text>
                            </>
                        )}
                    </TouchableOpacity>
                </View>
            </View>
        </SafeAreaView>
    );
}
