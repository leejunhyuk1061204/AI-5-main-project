import React, { useState, useMemo } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ActivityIndicator, KeyboardAvoidingView, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons } from '@expo/vector-icons';
import { useAlertStore } from '../store/useAlertStore';
import ocrApi, { OcrAnalysisResponse, MaintenanceLineItem } from '../api/ocrApi';
import { formatInputWithCommas, parseFormattedNumber } from '../utils/formatNumber';
import { useConsumableStore } from '../store/useConsumableStore';
import { isPositionTypeRow } from './consumableItems';
import MaintenanceForm, { type MaintenanceFormRow } from './MaintenanceForm';
import FuelingForm from './FuelingForm';

export default function ReceiptResult({ navigation, route }: { navigation?: any; route?: any }) {
    const { vehicleId, imageUri, ocrResult, initialType } = route?.params || {};
    const result: OcrAnalysisResponse = ocrResult || {};
    const consumablePickerList = useConsumableStore((s) => s.consumablePickerList);

    // 초기 타입 결정 (파라미터 > OCR 결과 > 기본값)
    const isFueling = initialType === 'FUELING' || result.receiptType === 'FUELING';

    const getItemNameByCode = (code: string) =>
        consumablePickerList.find((i) => i.code === code)?.name ?? '기타 정비';

    const rawCode = result.consumableItemCode || '';
    const initialPositionsFromResult = (() => {
        if (['TIRE_FL', 'TIRE_FR', 'TIRE_RL', 'TIRE_RR'].includes(rawCode)) return [rawCode];
        if (['BRAKE_PAD_FRONT', 'BRAKE_PAD_REAR'].includes(rawCode)) return [rawCode];
        return [];
    })();

    const initialMaintenanceRows = useMemo((): MaintenanceFormRow[] => {
        if (result.items && result.items.length > 0) {
            return result.items.map((item: MaintenanceLineItem, i: number) => ({
                id: `item-${i}-${Date.now()}`,
                consumableItemCode: item.consumableItemCode || 'OTHER',
                consumableItemName: item.consumableItemName ?? getItemNameByCode(item.consumableItemCode || ''),
                quantity: String(item.quantity ?? 1),
                amount: item.amount != null ? formatInputWithCommas(String(item.amount)) : '',
                positionCodes: undefined,
            }));
        }
        const code = rawCode === 'TIRES' || ['TIRE_FL', 'TIRE_FR', 'TIRE_RL', 'TIRE_RR'].includes(rawCode)
            ? 'TIRE_POSITION'
            : rawCode === 'BRAKE_PADS' || ['BRAKE_PAD_FRONT', 'BRAKE_PAD_REAR'].includes(rawCode)
                ? 'BRAKE_POSITION'
                : consumablePickerList.some((i) => i.code === rawCode)
                    ? rawCode
                    : 'OTHER';
        return [{
            id: `single-${Date.now()}`,
            consumableItemCode: code,
            consumableItemName: getItemNameByCode(code),
            quantity: String(result.quantity ?? 1),
            amount: result.cost != null ? formatInputWithCommas(String(result.cost)) : '',
            positionCodes: initialPositionsFromResult.length > 0 ? initialPositionsFromResult : undefined,
        }];
    }, []);

    // 공통 상태
    const [shopName, setShopName] = useState(result.shopName || '');
    const [date, setDate] = useState(result.maintenanceDate || new Date().toISOString().split('T')[0]);
    const [cost, setCost] = useState(result.cost ? formatInputWithCommas(result.cost.toString()) : '');
    const [mileage, setMileage] = useState(result.mileageAtMaintenance ? formatInputWithCommas(result.mileageAtMaintenance.toString()) : '');
    const [memo, setMemo] = useState('');
    const [isSaving, setIsSaving] = useState(false);

    // 정비 전용: 품목 목록 (MaintenanceForm이 제어)
    const [maintenanceRows, setMaintenanceRows] = useState<MaintenanceFormRow[]>(initialMaintenanceRows);

    // 주유 전용 상태
    const [fuelType, setFuelType] = useState(result.fuelType || 'GASOLINE');
    const [unitPrice, setUnitPrice] = useState(result.unitPrice ? formatInputWithCommas(result.unitPrice.toString()) : '');
    const [fuelAmount, setFuelAmount] = useState(result.fuelAmount ? result.fuelAmount.toString() : '');

    const handleSave = async () => {
        if (!vehicleId) {
            useAlertStore.getState().showAlert('오류', '차량 정보가 없습니다.', 'ERROR');
            return;
        }

        if (!isFueling) {
            const hasPositionRowWithoutSelection = maintenanceRows.some(r =>
                (r.consumableItemCode === 'TIRE_POSITION' || r.consumableItemCode === 'BRAKE_POSITION') && (!r.positionCodes || r.positionCodes.length === 0)
            );
            if (hasPositionRowWithoutSelection) {
                useAlertStore.getState().showAlert('위치 선택', '타이어/브레이크 항목에 교체한 위치를 선택해 주세요.', 'INFO');
                return;
            }
        }

        setIsSaving(true);
        try {
            if (isFueling) {
                const payload = {
                    fuelingDate: date,
                    mileageAtFueling: parseFormattedNumber(mileage),
                    fuelType,
                    amount: parseFloat(fuelAmount) || 0,
                    unitPrice: parseFormattedNumber(unitPrice),
                    totalCost: parseFormattedNumber(cost),
                    shopName,
                    memo,
                    receiptId: null
                };
                await ocrApi.registerFuelingManual(vehicleId, payload);
            } else {
                const base = {
                    maintenanceDate: date || new Date().toISOString().split('T')[0],
                    mileageAtMaintenance: parseFormattedNumber(mileage) || null,
                    shopName: shopName || null,
                    memo: memo || null,
                };
                const requests: Array<{ maintenanceDate: string; mileageAtMaintenance: number | null; shopName: string | null; memo: string | null; consumableItemCode: string; quantity: number; cost: number | null }> = [];
                for (const row of maintenanceRows) {
                    const positionCodesToUse = row.positionCodes?.length ? row.positionCodes : (isPositionTypeRow(row.consumableItemCode) && ['TIRE_FL', 'TIRE_FR', 'TIRE_RL', 'TIRE_RR', 'BRAKE_PAD_FRONT', 'BRAKE_PAD_REAR'].includes(row.consumableItemCode) ? [row.consumableItemCode] : null);
                    if (positionCodesToUse && positionCodesToUse.length > 0) {
                        const rowCost = row.amount ? Math.round(parseFormattedNumber(row.amount)) : null;
                        const costPer = rowCost != null ? Math.floor(rowCost / positionCodesToUse.length) : null;
                        for (const code of positionCodesToUse) {
                            requests.push({ ...base, consumableItemCode: code, quantity: 1, cost: costPer });
                        }
                    } else {
                        requests.push({
                            ...base,
                            consumableItemCode: row.consumableItemCode,
                            quantity: parseInt(row.quantity, 10) || 1,
                            cost: row.amount ? Math.round(parseFormattedNumber(row.amount)) : null,
                        });
                    }
                }
                await ocrApi.registerMaintenanceManual(vehicleId, requests);
            }

            useAlertStore.getState().showAlert(
                '저장 완료',
                isFueling ? '주유 기록이 저장되었습니다.' : '정비 이력이 저장되었습니다.',
                'SUCCESS',
                () => {
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

    return (
        <SafeAreaView className="flex-1 bg-background-dark">
            <StatusBar style="light" />

            <View className="flex-row items-center justify-between px-4 py-3 border-b border-white/5">
                <TouchableOpacity
                    onPress={() => navigation.goBack()}
                    className="w-10 h-10 items-center justify-center rounded-full active:bg-white/10"
                >
                    <MaterialIcons name="arrow-back-ios" size={20} color="white" />
                </TouchableOpacity>
                <Text className="text-white text-lg font-bold">
                    {isFueling ? '주유 분석 결과' : '정비 분석 결과'}
                </Text>
                <View className="w-10" />
            </View>

            <KeyboardAvoidingView
                behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
                className="flex-1"
            >
                <ScrollView className="flex-1" contentContainerStyle={{ paddingBottom: 120 }}>
                    {isFueling ? (
                        <FuelingForm
                            imageUri={imageUri}
                            date={date}
                            mileage={mileage}
                            shopName={shopName}
                            memo={memo}
                            fuelType={fuelType}
                            unitPrice={unitPrice}
                            fuelAmount={fuelAmount}
                            totalCost={cost}
                            onDateChange={setDate}
                            onMileageChange={setMileage}
                            onShopNameChange={setShopName}
                            onMemoChange={setMemo}
                            onFuelTypeChange={setFuelType}
                            onUnitPriceChange={setUnitPrice}
                            onFuelAmountChange={setFuelAmount}
                            onTotalCostChange={setCost}
                        />
                    ) : (
                        <MaintenanceForm
                            imageUri={imageUri}
                            date={date}
                            mileage={mileage}
                            shopName={shopName}
                            memo={memo}
                            items={maintenanceRows}
                            onDateChange={setDate}
                            onMileageChange={setMileage}
                            onShopNameChange={setShopName}
                            onMemoChange={setMemo}
                            onItemsChange={setMaintenanceRows}
                        />
                    )}
                </ScrollView>
            </KeyboardAvoidingView>

            {/* 하단 버튼 */}
            <View className="absolute bottom-0 left-0 right-0 bg-background-dark border-t border-white/5 px-5 py-4 pb-8">
                <View className="flex-row gap-3">
                    <TouchableOpacity
                        className="flex-1 bg-[#1e2936] py-4 rounded-xl items-center"
                        onPress={() => navigation.goBack()}
                        disabled={isSaving}
                    >
                        <Text className="text-white font-bold">재촬영</Text>
                    </TouchableOpacity>

                    <TouchableOpacity
                        className={`flex-[2] py-4 rounded-xl items-center flex-row justify-center gap-2 ${isFueling ? 'bg-orange-500' : 'bg-primary'}`}
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
