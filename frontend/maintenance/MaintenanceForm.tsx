import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Image, TextInput, Modal, Pressable } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useAlertStore } from '../store/useAlertStore';
import { formatInputWithCommas, parseFormattedNumber } from '../utils/formatNumber';
import { useConsumableStore } from '../store/useConsumableStore';
import { TIRE_POSITION_OPTIONS, BRAKE_POSITION_OPTIONS, isPositionTypeRow, getPositionOptions } from './consumableItems';

export type MaintenanceFormRow = {
    id: string;
    consumableItemCode: string;
    consumableItemName: string;
    quantity: string;
    amount: string;
    positionCodes?: string[];
};

export type MaintenanceFormProps = {
    imageUri?: string | null;
    date: string;
    mileage: string;
    shopName: string;
    memo: string;
    items: MaintenanceFormRow[];
    onDateChange: (v: string) => void;
    onMileageChange: (v: string) => void;
    onShopNameChange: (v: string) => void;
    onMemoChange: (v: string) => void;
    onItemsChange: (items: MaintenanceFormRow[]) => void;
};

export default function MaintenanceForm({
    imageUri,
    date,
    mileage,
    shopName,
    memo,
    items,
    onDateChange,
    onMileageChange,
    onShopNameChange,
    onMemoChange,
    onItemsChange,
}: MaintenanceFormProps) {
    const consumablePickerList = useConsumableStore((s) => s.consumablePickerList);
    const [editingItemRowId, setEditingItemRowId] = useState<string | null>(null);
    const [editingPositionRowId, setEditingPositionRowId] = useState<string | null>(null);

    const getItemNameByCode = (code: string) =>
        consumablePickerList.find((i) => i.code === code)?.name ?? '기타 정비';

    const editingPositionRow = editingPositionRowId ? items.find((r) => r.id === editingPositionRowId) : null;
    const positionOptionsForModal = editingPositionRow
        ? (editingPositionRow.consumableItemCode === 'TIRE_POSITION' || ['TIRE_FL', 'TIRE_FR', 'TIRE_RL', 'TIRE_RR'].includes(editingPositionRow.consumableItemCode) ? TIRE_POSITION_OPTIONS : BRAKE_POSITION_OPTIONS)
        : TIRE_POSITION_OPTIONS;

    const addRow = () => {
        onItemsChange([
            ...items,
            {
                id: `new-${Date.now()}`,
                consumableItemCode: 'OTHER',
                consumableItemName: '기타 정비',
                quantity: '1',
                amount: '',
                positionCodes: undefined,
            },
        ]);
    };

    const removeRow = (id: string) => {
        if (items.length <= 1) return;
        onItemsChange(items.filter((r) => r.id !== id));
        if (editingItemRowId === id) setEditingItemRowId(null);
        if (editingPositionRowId === id) setEditingPositionRowId(null);
    };

    const updateRow = (id: string, field: keyof MaintenanceFormRow, value: string | string[]) => {
        onItemsChange(
            items.map((r) => {
                if (r.id !== id) return r;
                if (field === 'consumableItemCode') {
                    const code = value as string;
                    return { ...r, consumableItemCode: code, consumableItemName: getItemNameByCode(code), positionCodes: undefined };
                }
                if (field === 'quantity') return { ...r, quantity: value as string };
                if (field === 'amount') return { ...r, amount: value as string };
                if (field === 'positionCodes') return { ...r, positionCodes: value as string[] };
                return r;
            })
        );
    };

    const togglePositionForRow = (code: string) => {
        if (!editingPositionRowId) return;
        const row = items.find((r) => r.id === editingPositionRowId);
        if (!row) return;
        const current = row.positionCodes || [];
        const next = current.includes(code) ? current.filter((c) => c !== code) : [...current, code];
        updateRow(editingPositionRowId, 'positionCodes', next);
    };

    const getTotalCost = () => items.reduce((sum, r) => sum + (r.amount ? parseFormattedNumber(r.amount) : 0), 0);

    const getDisplayNameForRow = (row: MaintenanceFormRow) => {
        const c = row.consumableItemCode;
        if (['TIRE_FL', 'TIRE_FR', 'TIRE_RL', 'TIRE_RR'].includes(c)) return '타이어 (위치 선택)';
        if (['BRAKE_PAD_FRONT', 'BRAKE_PAD_REAR'].includes(c)) return '브레이크 패드 (위치 선택)';
        return row.consumableItemName;
    };

    const isRowSelectedInPicker = (row: MaintenanceFormRow, itemCode: string) => {
        if (row.consumableItemCode === itemCode) return true;
        if (itemCode === 'TIRE_POSITION' && ['TIRE_FL', 'TIRE_FR', 'TIRE_RL', 'TIRE_RR'].includes(row.consumableItemCode)) return true;
        if (itemCode === 'BRAKE_POSITION' && ['BRAKE_PAD_FRONT', 'BRAKE_PAD_REAR'].includes(row.consumableItemCode)) return true;
        return false;
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
                        <Text className="text-text-dim text-xs mb-2">정비소</Text>
                        <TextInput
                            className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white"
                            value={shopName}
                            onChangeText={onShopNameChange}
                            placeholder="정비소 이름"
                            placeholderTextColor="#64748b"
                        />
                    </View>
                    <View>
                        <Text className="text-text-dim text-xs mb-2">정비일</Text>
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
                    <Text className="text-text-dim text-xs mb-2">정비 항목</Text>
                    {items.map((row) => (
                        <View key={row.id} className="gap-2 mb-3">
                            <View className="flex-row gap-2 items-end">
                                {/* 품목 40% - min-w-0·overflow-hidden으로 겹침 방지 */}
                                <View className="flex-[2] min-w-0 overflow-hidden">
                                    <Text className="text-text-dim text-[10px] mb-1">품목</Text>
                                    <TouchableOpacity
                                        className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 flex-row justify-between items-center min-h-[44px]"
                                        onPress={() => setEditingItemRowId(editingItemRowId === row.id ? null : row.id)}
                                    >
                                        <Text className="text-white flex-1 min-w-0" numberOfLines={1}>{getDisplayNameForRow(row)}</Text>
                                        <MaterialIcons name="arrow-drop-down" size={24} color="#94a3b8" />
                                    </TouchableOpacity>
                                </View>
                                {/* 나머지 60% - min-w-0으로 겹침 방지 */}
                                <View className="flex-[3] min-w-0 overflow-hidden flex-row gap-2 items-end">
                                    <View className="w-16 shrink-0">
                                        <Text className="text-text-dim text-[10px] mb-1">수량</Text>
                                        <TextInput
                                            className="bg-white/5 border border-white/10 rounded-xl px-1 py-3 text-white text-center min-h-[44px]"
                                            value={row.quantity}
                                            onChangeText={(v) => updateRow(row.id, 'quantity', v.replace(/[^0-9]/g, ''))}
                                            keyboardType="number-pad"
                                            placeholder="1"
                                            placeholderTextColor="#64748b"
                                        />
                                    </View>
                                    <View className="flex-1 min-w-0">
                                        <Text className="text-text-dim text-[10px] mb-1">금액</Text>
                                        <TextInput
                                            className="bg-white/5 border border-white/10 rounded-xl px-2 py-3 text-white text-right min-h-[44px]"
                                            value={row.amount}
                                            onChangeText={(v) => updateRow(row.id, 'amount', formatInputWithCommas(v))}
                                            keyboardType="numeric"
                                            placeholder="0"
                                            placeholderTextColor="#64748b"
                                        />
                                    </View>
                                    {items.length > 1 ? (
                                        <View className="w-12 shrink-0 self-end">
                                            <View className="h-4" />
                                            <TouchableOpacity
                                                onPress={() => removeRow(row.id)}
                                                className="min-h-[44px] rounded-xl bg-red-500/10 border border-red-500/20 items-center justify-center"
                                            >
                                                <MaterialIcons name="remove" size={20} color="#ef4444" />
                                            </TouchableOpacity>
                                        </View>
                                    ) : null}
                                </View>
                            </View>
                            {editingItemRowId === row.id && (
                                <View className="bg-surface-dark border border-white/10 rounded-xl mt-1 overflow-hidden max-h-44">
                                    <ScrollView nestedScrollEnabled>
                                        {consumablePickerList.map((item) => (
                                            <TouchableOpacity
                                                key={item.code}
                                                className={`px-4 py-3 border-b border-white/5 ${isRowSelectedInPicker(row, item.code) ? 'bg-primary/20' : ''}`}
                                                onPress={() => {
                                                    updateRow(row.id, 'consumableItemCode', item.code);
                                                    setEditingItemRowId(null);
                                                    if (item.code === 'TIRE_POSITION' || item.code === 'BRAKE_POSITION') {
                                                        setEditingPositionRowId(row.id);
                                                    }
                                                }}
                                            >
                                                <Text className={isRowSelectedInPicker(row, item.code) ? 'text-primary font-bold' : 'text-white'}>{item.name}</Text>
                                            </TouchableOpacity>
                                        ))}
                                    </ScrollView>
                                </View>
                            )}
                            {isPositionTypeRow(row.consumableItemCode) && (
                                <TouchableOpacity
                                    className="flex-row items-center gap-2 bg-white/5 border border-white/10 rounded-xl px-4 py-2 mt-1"
                                    onPress={() => setEditingPositionRowId(editingPositionRowId === row.id ? null : row.id)}
                                >
                                    <MaterialIcons name="edit" size={18} color="#94a3b8" />
                                    <Text className="text-text-dim text-sm">
                                        {(row.positionCodes?.length || (['TIRE_FL', 'TIRE_FR', 'TIRE_RL', 'TIRE_RR', 'BRAKE_PAD_FRONT', 'BRAKE_PAD_REAR'].includes(row.consumableItemCode) ? 1 : 0))
                                            ? `선택: ${(row.positionCodes?.length ? row.positionCodes : [row.consumableItemCode]).map((c) => getPositionOptions(row.consumableItemCode).find((o) => o.code === c)?.name).filter(Boolean).join(', ')}`
                                            : '위치 선택 (탭하여 선택)'}
                                    </Text>
                                </TouchableOpacity>
                            )}
                        </View>
                    ))}
                    <TouchableOpacity
                        onPress={addRow}
                        className="flex-row items-center justify-center gap-2 py-3 bg-white/5 rounded-xl border border-white/10 border-dashed mb-2"
                    >
                        <MaterialIcons name="add" size={20} color="#94a3b8" />
                        <Text className="text-text-dim">항목 추가</Text>
                    </TouchableOpacity>
                    <View className="flex-row justify-between items-center bg-primary/10 p-4 rounded-xl border border-primary/20">
                        <Text className="text-primary font-bold">총 정비 비용</Text>
                        <Text className="text-white font-bold text-lg">{getTotalCost().toLocaleString()}원</Text>
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

            <Modal visible={editingPositionRowId != null} transparent animationType="fade" onRequestClose={() => setEditingPositionRowId(null)}>
                <Pressable className="flex-1 bg-black/60 justify-center px-6" onPress={() => setEditingPositionRowId(null)}>
                    <Pressable className="bg-surface-dark border border-white/10 rounded-2xl p-5" onPress={(e) => e.stopPropagation()}>
                        <Text className="text-white font-bold text-lg mb-1">
                            {editingPositionRow?.consumableItemCode === 'TIRE_POSITION' || ['TIRE_FL', 'TIRE_FR', 'TIRE_RL', 'TIRE_RR'].includes(editingPositionRow?.consumableItemCode ?? '')
                                ? '어느 타이어를 교체했나요?'
                                : '어느 브레이크 패드를 교체했나요?'}
                        </Text>
                        <Text className="text-text-dim text-sm mb-4">복수 선택 가능</Text>
                        <View className="gap-2 mb-5">
                            {positionOptionsForModal.map((opt) => {
                                const row = editingPositionRowId ? items.find((r) => r.id === editingPositionRowId) : null;
                                const selected = row?.positionCodes?.includes(opt.code) ?? false;
                                return (
                                    <TouchableOpacity
                                        key={opt.code}
                                        className={`flex-row items-center gap-3 px-4 py-3 rounded-xl border ${selected ? 'bg-primary/20 border-primary' : 'bg-white/5 border-white/10'}`}
                                        onPress={() => togglePositionForRow(opt.code)}
                                    >
                                        <MaterialIcons name={selected ? 'check-box' : 'check-box-outline-blank'} size={24} color={selected ? '#3b82f6' : '#64748b'} />
                                        <Text className={selected ? 'text-white font-semibold' : 'text-text-dim'}>{opt.name}</Text>
                                    </TouchableOpacity>
                                );
                            })}
                        </View>
                        <View className="flex-row gap-3">
                            <TouchableOpacity className="flex-1 py-3 rounded-xl bg-white/10 items-center" onPress={() => setEditingPositionRowId(null)}>
                                <Text className="text-white">취소</Text>
                            </TouchableOpacity>
                            <TouchableOpacity
                                className="flex-1 py-3 rounded-xl bg-primary items-center"
                                onPress={() => {
                                    const row = editingPositionRowId ? items.find((r) => r.id === editingPositionRowId) : null;
                                    if (row?.positionCodes && row.positionCodes.length > 0) setEditingPositionRowId(null);
                                    else useAlertStore.getState().showAlert('알림', '최소 1개 위치를 선택해 주세요.', 'INFO');
                                }}
                                disabled={!(editingPositionRow?.positionCodes?.length)}
                            >
                                <Text className="text-white font-bold">선택 완료</Text>
                            </TouchableOpacity>
                        </View>
                    </Pressable>
                </Pressable>
            </Modal>
        </>
    );
}
