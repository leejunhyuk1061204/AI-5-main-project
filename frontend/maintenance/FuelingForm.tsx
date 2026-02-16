import React from 'react';
import { View, Text, TextInput, Image } from 'react-native';
import { TouchableOpacity } from 'react-native';
import { formatInputWithCommas, parseFormattedNumber } from '../utils/formatNumber';

const FUEL_TYPE_NAMES: { [key: string]: string } = {
    GASOLINE: '휘발유',
    DIESEL: '경유',
    LPG: 'LPG',
    EV: '전기',
};

export type FuelingFormProps = {
    imageUri?: string | null;
    date: string;
    mileage: string;
    shopName: string;
    memo: string;
    fuelType: string;
    unitPrice: string;
    fuelAmount: string;
    totalCost: string;
    onDateChange: (v: string) => void;
    onMileageChange: (v: string) => void;
    onShopNameChange: (v: string) => void;
    onMemoChange: (v: string) => void;
    onFuelTypeChange: (v: string) => void;
    onUnitPriceChange: (v: string) => void;
    onFuelAmountChange: (v: string) => void;
    onTotalCostChange: (v: string) => void;
};

export default function FuelingForm({
    imageUri,
    date,
    mileage,
    shopName,
    memo,
    fuelType,
    unitPrice,
    fuelAmount,
    totalCost,
    onDateChange,
    onMileageChange,
    onShopNameChange,
    onMemoChange,
    onFuelTypeChange,
    onUnitPriceChange,
    onFuelAmountChange,
    onTotalCostChange,
}: FuelingFormProps) {
    const handleUnitPriceChange = (value: string) => {
        const formatted = formatInputWithCommas(value);
        onUnitPriceChange(formatted);
        if (fuelAmount) {
            const total = parseFormattedNumber(formatted) * parseFloat(fuelAmount);
            onTotalCostChange(formatInputWithCommas(Math.round(total).toString()));
        }
    };

    const handleFuelAmountChange = (value: string) => {
        onFuelAmountChange(value);
        if (unitPrice) {
            const total = parseFormattedNumber(unitPrice) * parseFloat(value);
            onTotalCostChange(formatInputWithCommas(Math.round(total).toString()));
        }
    };

    return (
        <>
            {imageUri ? (
                <View className="px-5 pt-4">
                    <Text className="text-[13px] font-semibold text-text-dim uppercase tracking-widest mb-3">원본 영수증</Text>
                    <View className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden h-48 items-center justify-center">
                        <Image source={{ uri: imageUri }} className="w-full h-full" resizeMode="contain" />
                    </View>
                </View>
            ) : null}

            <View className="px-5 pt-6 gap-4">
                <View className="bg-white/5 border border-white/10 rounded-2xl p-4 gap-4">
                    <View>
                        <Text className="text-text-dim text-xs mb-2">주유소</Text>
                        <TextInput
                            className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white"
                            value={shopName}
                            onChangeText={onShopNameChange}
                            placeholder="주유소 이름"
                            placeholderTextColor="#64748b"
                        />
                    </View>
                    <View>
                        <Text className="text-text-dim text-xs mb-2">주유일</Text>
                        <TextInput
                            className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white"
                            value={date}
                            onChangeText={onDateChange}
                            placeholder="YYYY-MM-DD"
                            placeholderTextColor="#64748b"
                        />
                    </View>
                    <View>
                        <Text className="text-text-dim text-xs mb-2">주행거리 (km)</Text>
                        <TextInput
                            className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white"
                            value={mileage}
                            onChangeText={(v) => onMileageChange(formatInputWithCommas(v))}
                            placeholder="0"
                            placeholderTextColor="#64748b"
                            keyboardType="numeric"
                        />
                    </View>
                </View>

                <View className="bg-white/5 border border-white/10 rounded-2xl p-4 gap-4">
                    <View>
                        <Text className="text-text-dim text-xs mb-2">유종</Text>
                        <View className="flex-row flex-wrap gap-2">
                            {Object.entries(FUEL_TYPE_NAMES).map(([code, name]) => (
                                <TouchableOpacity
                                    key={code}
                                    onPress={() => onFuelTypeChange(code)}
                                    className={`px-3 py-2 rounded-lg border ${fuelType === code ? 'bg-orange-500 border-orange-500' : 'bg-white/5 border-white/10'}`}
                                >
                                    <Text className={fuelType === code ? 'text-white font-bold' : 'text-text-dim'}>{name}</Text>
                                </TouchableOpacity>
                            ))}
                        </View>
                    </View>

                    <View className="flex-row gap-3">
                        <View className="flex-1">
                            <Text className="text-text-dim text-xs mb-2">단가 (원)</Text>
                            <TextInput
                                className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white"
                                value={unitPrice}
                                onChangeText={handleUnitPriceChange}
                                placeholder="0"
                                placeholderTextColor="#64748b"
                                keyboardType="numeric"
                            />
                        </View>
                        <View className="flex-1">
                            <Text className="text-text-dim text-xs mb-2">주유량 (L)</Text>
                            <TextInput
                                className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white"
                                value={fuelAmount}
                                onChangeText={handleFuelAmountChange}
                                placeholder="0"
                                placeholderTextColor="#64748b"
                                keyboardType="numeric"
                            />
                        </View>
                    </View>

                    <View>
                        <Text className="text-text-dim text-xs mb-2">총 결제금액 (원)</Text>
                        <TextInput
                            className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white font-bold text-lg"
                            value={totalCost}
                            onChangeText={(v) => onTotalCostChange(formatInputWithCommas(v))}
                            placeholder="0"
                            placeholderTextColor="#64748b"
                            keyboardType="numeric"
                        />
                    </View>
                </View>

                <View>
                    <Text className="text-text-dim text-xs mb-2">메모</Text>
                    <TextInput
                        className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white h-24"
                        value={memo}
                        onChangeText={onMemoChange}
                        placeholder="메모 입력"
                        placeholderTextColor="#64748b"
                        multiline
                        textAlignVertical="top"
                    />
                </View>
            </View>
        </>
    );
}
