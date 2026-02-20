import React, { useMemo } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { MaintenanceHistoryResponse, FuelingHistoryResponse } from '../api/ocrApi';

// 통합 이력 아이템 타입
export interface CombinedHistoryItem {
    id: string;
    date: string;         // 날짜 (YYYY-MM-DD)
    type: 'MAINTENANCE' | 'FUELING';
    title: string;        // 항목명 또는 유종
    shopName: string;     // 장소
    cost: number;         // 비용
    mileage: number | null; // 주행거리
    data: any;            // 원본 데이터 (상세보기용)
}

interface AllHistoryListProps {
    maintenanceList: MaintenanceHistoryResponse[];         // 원본 정비 데이터 (그룹화 전)
    fuelingList: FuelingHistoryResponse[];
    filterType: 'ALL' | 'MAINTENANCE' | 'FUELING';
    sortOrder: 'date' | 'cost';
    onItemClick: (item: CombinedHistoryItem) => void;
}

// 날짜 포맷팅 (MM/DD)
const formatDate = (dateStr: string) => {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return `${date.getMonth() + 1}/${date.getDate()}`; // MM/DD 형식
};

// 비용 포맷팅
const formatCost = (cost: number) => {
    return `${cost.toLocaleString()}원`;
};

// 유종 표시명 변환
const getFuelTypeName = (fuelType: string) => {
    switch (fuelType) {
        case 'EV': return '전기 충전';
        case 'DIESEL': return '경유';
        case 'GASOLINE': return '휘발유';
        case 'LPG': return 'LPG';
        default: return fuelType;
    }
};

export default function AllHistoryList({
    maintenanceList,
    fuelingList,
    filterType,
    sortOrder,
    onItemClick
}: AllHistoryListProps) {

    // 데이터 통합 및 가공
    const combinedList = useMemo(() => {
        const list: CombinedHistoryItem[] = [];

        // 1. 정비 이력 변환 (단일 항목 기준)
        // 기존 MaintenanceBook에서는 그룹화를 했지만, 전체보기에서는 개별 항목으로 보여주는 것이 일반적일 수 있음.
        // 하지만 사용자가 그룹별 상세를 보길 원할 수 있으므로, 여기서는 "정비 내역"을 그룹 단위로 보여줄지, 개별로 보여줄지 결정해야 함.
        // 기획 상 "통합 목록"이므로 정비는 건별(그룹별)로 묶어서 보여주는 것이 깔끔함 (영수증 1장 = 1개 항목).
        // MaintenanceBook의 그룹화 로직을 여기서도 일부 차용하거나, Props로 이미 그룹화된 데이터를 받는 것이 좋음.
        // 일단 원본 데이터를 받아서 여기서 그룹화 로직을 수행하도록 함 (독립성 보장).

        // 정비 이력 그룹화
        const groupedMaintenance = maintenanceList.reduce((acc: any[], item) => {
            const key = item.receiptId || item.id;
            const existing = acc.find(g => g.receiptId === key);
            if (existing) {
                existing.items.push(item);
                existing.cost += item.cost || 0;
            } else {
                acc.push({
                    receiptId: key,
                    date: item.maintenanceDate,
                    shopName: item.shopName,
                    cost: item.cost || 0,
                    mileage: item.mileageAtMaintenance,
                    items: [item],
                    original: item // 대표 아이템
                });
            }
            return acc;
        }, []);

        groupedMaintenance.forEach(group => {
            const first = group.items[0];
            const qtySuffix = (first.quantity != null && first.quantity > 1) ? ` x${first.quantity}` : '';
            const title = group.items.length > 1
                ? `${first.itemDescription} 외 ${group.items.length - 1}건`
                : `${first.itemDescription}${qtySuffix}`;

            list.push({
                id: `M-${group.receiptId}`,
                date: group.date,
                type: 'MAINTENANCE',
                title: title,
                shopName: group.shopName || '정비소 미기록',
                cost: group.cost,
                mileage: group.mileage,
                data: { ...group, isFueling: false, totalCost: group.cost, maintenanceDate: group.date } // 상세 보기를 위한 데이터 구조 맞춤
            });
        });

        // 2. 주유 이력 변환
        fuelingList.forEach(item => {
            list.push({
                id: `F-${item.id}`,
                date: item.fuelingDate,
                type: 'FUELING',
                title: getFuelTypeName(item.fuelType),
                shopName: item.shopName || item.stationName || '주유소 미기록',
                cost: item.totalCost,
                mileage: item.mileageAtFueling,
                data: { ...item, isFueling: true }
            });
        });

        return list;
    }, [maintenanceList, fuelingList]);

    // 필터링 및 정렬
    const sortedList = useMemo(() => {
        let filtered = combinedList;

        if (filterType === 'MAINTENANCE') {
            filtered = filtered.filter(item => item.type === 'MAINTENANCE');
        } else if (filterType === 'FUELING') {
            filtered = filtered.filter(item => item.type === 'FUELING');
        }

        return filtered.sort((a, b) => {
            if (sortOrder === 'date') {
                return new Date(b.date).getTime() - new Date(a.date).getTime();
            } else {
                return b.cost - a.cost;
            }
        });
    }, [combinedList, filterType, sortOrder]);

    // 빈 상태 처리
    if (sortedList.length === 0) {
        return (
            <View className="items-center justify-center py-20">
                <MaterialIcons name="history" size={48} color="#334155" />
                <Text className="text-gray-500 text-sm mt-4">기록된 내역이 없습니다.</Text>
            </View>
        );
    }

    return (
        <View className="gap-3">
            {sortedList.map((item, index) => (
                <TouchableOpacity
                    key={item.id || index}
                    className="bg-white/5 border border-white/10 rounded-2xl p-4 active:bg-white/10"
                    onPress={() => onItemClick(item)}
                >
                    <View className="flex-row justify-between items-start mb-2">
                        <View className="flex-row items-center gap-3">
                            {/* 아이콘: 타입에 따라 색상/아이콘 변경 */}
                            <View className={`w-10 h-10 rounded-xl items-center justify-center ${item.type === 'MAINTENANCE' ? 'bg-primary/20' : 'bg-orange-500/20'}`}>
                                <MaterialIcons
                                    name={item.type === 'MAINTENANCE' ? 'build' : 'local-gas-station'}
                                    size={20}
                                    color={item.type === 'MAINTENANCE' ? '#0d7ff2' : '#f97316'}
                                />
                            </View>
                            <View>
                                <Text className="text-white font-bold text-base">
                                    {item.title}
                                </Text>
                                <Text className="text-text-dim text-xs">
                                    {item.shopName}
                                </Text>
                            </View>
                        </View>
                        <View className="items-end">
                            <Text className={`font-bold ${item.type === 'MAINTENANCE' ? 'text-primary' : 'text-orange-500'}`}>
                                {formatCost(item.cost)}
                            </Text>
                            <Text className="text-text-dim text-[10px] mt-1">
                                {formatDate(item.date)}
                            </Text>
                        </View>
                    </View>
                </TouchableOpacity>
            ))}
        </View>
    );
}
