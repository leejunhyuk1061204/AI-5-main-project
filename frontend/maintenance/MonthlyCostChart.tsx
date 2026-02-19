import React, { useMemo, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { MaintenanceHistoryResponse, FuelingHistoryResponse } from '../api/ocrApi';

// 월간 비용 집계 인터페이스
interface MonthlyCost {
    month: string; // 'YYYY-MM' 형식
    monthLabel: string; // 'MM월' 표시용
    maintenanceCost: number;
    fuelingCost: number;
    totalCost: number;
}

interface MonthlyCostChartProps {
    maintenanceList: MaintenanceHistoryResponse[];
    fuelingList: FuelingHistoryResponse[];
}

export default function MonthlyCostChart({ maintenanceList, fuelingList }: MonthlyCostChartProps) {
    const [periodFilter, setPeriodFilter] = useState<3 | 6 | 12>(6); // 기본 6개월
    const [chartType, setChartType] = useState<'ALL' | 'MAINTENANCE' | 'FUELING'>('ALL'); // 기본 전체

    // 기간 변경 핸들러
    const onPeriodChange = (period: 3 | 6 | 12) => {
        setPeriodFilter(period);
    };

    // 월별 데이터 집계 (useMemo로 최적화)
    const monthlyCosts = useMemo(() => {
        const today = new Date();
        const currentYear = today.getFullYear();
        const currentMonth = today.getMonth() + 1; // 1-12

        // 결과 맵 초기화 (최근 N개월)
        const costsMap: { [key: string]: { maintenance: number; fueling: number } } = {};

        // 날짜 파싱 헬퍼 (YYYY-MM-DD -> Date)
        const parseDate = (dateStr: string) => {
            const parts = dateStr.split('-');
            return new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
        };

        // 필터 시작 날짜 계산
        const filterStartDate = new Date(currentYear, currentMonth - 1 - periodFilter + 1, 1);

        for (let i = periodFilter - 1; i >= 0; i--) {
            const date = new Date(currentYear, currentMonth - 1 - i, 1);
            const year = date.getFullYear();
            const month = date.getMonth() + 1;
            const monthKey = `${year}-${String(month).padStart(2, '0')}`;
            costsMap[monthKey] = { maintenance: 0, fueling: 0 };
        }

        // 1. 정비 내역 집계 (날짜 없으면 스킵, 필터링 기간 내)
        maintenanceList.forEach((item) => {
            if (!item.maintenanceDate) return;
            const date = parseDate(item.maintenanceDate);
            if (date < filterStartDate) return; // Filter out dates older than the period

            const monthKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;

            if (costsMap[monthKey]) { // Only add if month is within the filtered period
                costsMap[monthKey].maintenance += item.cost || 0;
            }
        });

        // 2. 주유 내역 집계 (날짜 없으면 스킵, 필터링 기간 내)
        fuelingList.forEach((item) => {
            if (!item.fuelingDate) return;
            const date = parseDate(item.fuelingDate);
            if (date < filterStartDate) return; // Filter out dates older than the period

            const monthKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;

            if (costsMap[monthKey]) { // Only add if month is within the filtered period
                costsMap[monthKey].fueling += item.totalCost || 0;
            }
        });

        // Convert costsMap to MonthlyCost array, ensuring correct order and labels
        const result: MonthlyCost[] = [];
        const sortedMonthKeys = Object.keys(costsMap).sort(); // Sort keys to ensure chronological order

        sortedMonthKeys.forEach(monthKey => {
            const [year, month] = monthKey.split('-').map(Number);
            const monthLabel = `${month}월`;
            const maintenanceCost = costsMap[monthKey].maintenance;
            const fuelingCost = costsMap[monthKey].fueling;
            const totalCost = maintenanceCost + fuelingCost;

            result.push({
                month: monthKey,
                monthLabel,
                maintenanceCost,
                fuelingCost,
                totalCost
            });
        });

        return result;
    }, [maintenanceList, fuelingList, periodFilter]);

    // 통계 계산 (chartType에 따라 동적 계산)
    const monthlyCostStats = useMemo((): { avgMonthlyCost: number; totalCost: number; maxCostMonth: MonthlyCost | null } => {
        if (monthlyCosts.length === 0) return { avgMonthlyCost: 0, totalCost: 0, maxCostMonth: null };

        let totalCost = 0;
        let maxCost = -1;
        let maxCostMonth: MonthlyCost | null = null;

        let validMonthCount = 0;

        monthlyCosts.forEach(item => {
            let cost = 0;
            if (chartType === 'ALL') {
                cost = item.totalCost;
            } else if (chartType === 'MAINTENANCE') {
                cost = item.maintenanceCost;
            } else { // FUELING
                cost = item.fuelingCost;
            }

            totalCost += cost;
            if (cost > 0) {
                validMonthCount++;
            }

            if (cost > maxCost) {
                maxCost = cost;
                maxCostMonth = item;
            }
        });

        const avgMonthlyCost = validMonthCount > 0 ? Math.round(totalCost / validMonthCount) : 0;

        return { avgMonthlyCost, totalCost, maxCostMonth };
    }, [monthlyCosts, chartType]);

    // 차트 최대값 계산 (10만 단위 올림)
    const maxChartValue = useMemo(() => {
        let maxVal = 0;
        if (monthlyCosts.length > 0) {
            if (chartType === 'ALL') {
                maxVal = Math.max(...monthlyCosts.map(m => Math.max(m.maintenanceCost, m.fuelingCost)));
            } else if (chartType === 'MAINTENANCE') {
                maxVal = Math.max(...monthlyCosts.map(m => m.maintenanceCost));
            } else {
                maxVal = Math.max(...monthlyCosts.map(m => m.fuelingCost));
            }
        }

        // 10만 단위 올림, 최소 10만
        if (maxVal === 0) return 300000;
        return Math.ceil(maxVal / 100000) * 100000 + 100000; // 여유 공간
    }, [monthlyCosts, chartType]);

    // 그리드 라인 값 생성 (10만 단위)
    const gridLines = useMemo(() => {
        const lines = [];
        const step = 100000;
        for (let i = 0; i <= maxChartValue; i += step) {
            lines.push(i);
        }
        return lines;
    }, [maxChartValue]);

    // 상세 내역 데이터 준비
    const detailItems = useMemo(() => {
        // 기간 필터링 기준 날짜 계산 (현재 월 포함 과거 N개월)
        const today = new Date();
        const startYear = today.getFullYear();
        const startMonth = today.getMonth() - periodFilter + 1; // 예: 3개월이면 현재가 5월일 때 3, 4, 5월. 즉 3월부터.
        const startDate = new Date(startYear, startMonth, 1);
        const startDateStr = startDate.toISOString().split('T')[0].substring(0, 7); // 'YYYY-MM'

        if (chartType === 'ALL') {
            // 기간 내 총액 집계
            let maintTotal = 0;
            let fuelTotal = 0;

            // monthlyCosts는 이미 기간 필터링이 되어 있으므로 이를 활용
            monthlyCosts.forEach(item => {
                maintTotal += item.maintenanceCost;
                fuelTotal += item.fuelingCost;
            });

            return [
                { id: 'maint', label: '정비 합계', subLabel: null, amount: maintTotal, color: 'text-primary' },
                { id: 'fuel', label: '주유 합계', subLabel: null, amount: fuelTotal, color: 'text-orange-500' }
            ];
        } else if (chartType === 'MAINTENANCE') {
            // 정비 항목별 집계
            const itemMap = new Map<string, number>();
            maintenanceList.forEach(item => {
                // maintenanceDate가 null이면 건너뜀 (크래시 방지)
                if (!item.maintenanceDate) return;

                // maintenanceDate가 YYYY-MM-DD 형식이므로 YYYY-MM으로 비교
                if (item.maintenanceDate.substring(0, 7) >= startDateStr) {
                    const key = item.itemDescription || '기타 정비';
                    itemMap.set(key, (itemMap.get(key) || 0) + (item.cost || 0));
                }
            });
            return Array.from(itemMap.entries())
                .map(([label, amount]) => ({ id: label, label, subLabel: null, amount, color: 'text-white' }))
                .sort((a, b) => b.amount - a.amount);
        } else {
            // 주유 날짜별 집계 (최신순)
            return fuelingList
                .filter(item => {
                    if (!item.fuelingDate) return false;
                    return item.fuelingDate.substring(0, 7) >= startDateStr;
                })
                .sort((a, b) => (b.fuelingDate || '').localeCompare(a.fuelingDate || ''))
                .map(item => ({
                    id: item.id,
                    label: item.fuelingDate || '-',
                    subLabel: item.shopName || '주유소',
                    amount: item.totalCost ?? 0,
                    color: 'text-white'
                }));
        }
    }, [chartType, periodFilter, monthlyCosts, maintenanceList, fuelingList]);

    return (
        <View className="gap-2">
            {/* 월간 비용 차트 */}
            <View className="bg-white/5 border border-white/10 rounded-2xl p-3">
                {/* 헤더: 제목 및 기간 선택 버튼 */}
                <View className="flex-row justify-between items-center mb-2">
                    <Text className="text-white text-base font-bold">월간 비용</Text>
                    <View className="flex-row bg-black/20 rounded-lg p-0.5 border border-white/5">
                        {[3, 6, 12].map((period) => (
                            <TouchableOpacity
                                key={period}
                                onPress={() => onPeriodChange(period as 3 | 6 | 12)}
                                className={`px-2 py-1 rounded-md ${periodFilter === period ? 'bg-white/20' : 'bg-transparent'}`}
                            >
                                <Text className={`text-[10px] ${periodFilter === period ? 'text-white font-bold' : 'text-text-dim'}`}>
                                    {period === 12 ? '1년' : `${period}개월`}
                                </Text>
                            </TouchableOpacity>
                        ))}
                    </View>
                </View>

                {/* 차트 타입 필터 */}
                <View className="flex-row gap-2 mb-2">
                    <TouchableOpacity
                        onPress={() => setChartType('ALL')}
                        className={`px-3 py-1 rounded-full border ${chartType === 'ALL' ? 'bg-white/20 border-white/20' : 'bg-transparent border-white/10'}`}
                    >
                        <Text className={`text-[10px] ${chartType === 'ALL' ? 'text-white font-bold' : 'text-text-dim'}`}>전체</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                        onPress={() => setChartType('MAINTENANCE')}
                        className={`px-3 py-1 rounded-full border ${chartType === 'MAINTENANCE' ? 'bg-primary border-primary' : 'bg-transparent border-white/10'}`}
                    >
                        <Text className={`text-[10px] ${chartType === 'MAINTENANCE' ? 'text-white font-bold' : 'text-text-dim'}`}>정비</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                        onPress={() => setChartType('FUELING')}
                        className={`px-3 py-1 rounded-full border ${chartType === 'FUELING' ? 'bg-orange-500 border-orange-500' : 'bg-transparent border-white/10'}`}
                    >
                        <Text className={`text-[10px] ${chartType === 'FUELING' ? 'text-white font-bold' : 'text-text-dim'}`}>주유</Text>
                    </TouchableOpacity>
                </View>

                {/* 차트 및 축 영역 */}
                <View className="flex-row h-[360px] mt-2 mb-2">
                    {/* Y축 (레이블) */}
                    <View className="w-8 h-full relative justify-end mr-1">
                        {gridLines.map((val) => (
                            <Text
                                key={val}
                                className="absolute right-0 text-[9px] text-text-dim w-full text-right pr-1"
                                style={{ bottom: `${(val / maxChartValue) * 100}%`, marginBottom: -6 }} // 폰트 크기 고려해 중앙 정렬 보정
                            >
                                {val === 0 ? '0' : `${Math.floor(val / 10000)}`}
                            </Text>
                        ))}
                    </View>

                    {/* 차트 컨텐츠 영역 (그리드 + 막대) */}
                    <View className="flex-1 h-full relative border-l border-b border-white/20">
                        {/* 배경 그리드 라인 */}
                        {gridLines.map((val) => (
                            <View
                                key={val}
                                className="absolute w-full border-t border-white/10"
                                style={{
                                    bottom: `${(val / maxChartValue) * 100}%`,
                                    borderColor: val === 0 ? 'transparent' : 'rgba(255, 255, 255, 0.1)',
                                    borderStyle: 'solid'
                                }}
                            >
                            </View>
                        ))}

                        {/* 막대 그래프 컨테이너 */}
                        <View className="absolute inset-0 flex-row items-end justify-between px-1 w-full h-full gap-1">
                            {monthlyCosts.map((item) => (
                                <View key={item.month} className="flex-1 items-center gap-1 h-full justify-end pb-0">
                                    {/* 막대 영역 - 너비를 줄여 여백 확보 (w-full -> w-[85%]) */}
                                    <View className="w-[85%] flex-row items-end justify-center gap-0 h-full relative">

                                        {/* 정비 막대 */}
                                        {(chartType === 'ALL' || chartType === 'MAINTENANCE') && (
                                            <View className="items-center justify-end h-full flex-1">
                                                <View
                                                    className={`bg-primary rounded-t-sm w-full`}
                                                    style={{
                                                        height: `${Math.max((item.maintenanceCost / maxChartValue) * 100, 0)}%`,
                                                        minHeight: item.maintenanceCost > 0 ? 2 : 0,
                                                        opacity: item.maintenanceCost > 0 ? 1 : 0
                                                    }}
                                                />
                                            </View>
                                        )}

                                        {/* 주유 막대 */}
                                        {(chartType === 'ALL' || chartType === 'FUELING') && (
                                            <View className="items-center justify-end h-full flex-1">
                                                <View
                                                    className={`bg-orange-500 rounded-t-sm w-full`}
                                                    style={{
                                                        height: `${Math.max((item.fuelingCost / maxChartValue) * 100, 0)}%`,
                                                        minHeight: item.fuelingCost > 0 ? 0 : 0,
                                                        opacity: item.fuelingCost > 0 ? 1 : 0
                                                    }}
                                                />
                                            </View>
                                        )}
                                    </View>
                                    {/* 월 라벨 */}
                                    <Text className="text-text-secondary text-[8px] mt-1" numberOfLines={1}>{item.monthLabel}</Text>
                                </View>
                            ))}
                        </View>
                    </View>
                </View>

                {/* 범례 (ALL 일때만 표시) */}
                {chartType === 'ALL' && (
                    <View className="flex-row justify-center gap-3 mt-1">
                        <View className="flex-row items-center gap-1">
                            <View className="w-2.5 h-2.5 rounded-full bg-primary" />
                            <Text className="text-text-dim text-[10px]">정비</Text>
                        </View>
                        <View className="flex-row items-center gap-1">
                            <View className="w-2.5 h-2.5 rounded-full bg-orange-500" />
                            <Text className="text-text-dim text-[10px]">주유/충전</Text>
                        </View>
                    </View>
                )}
            </View>

            <View className="flex-row gap-2">
                {/* 통계 요약 */}
                <View className="flex-1 bg-white/5 border border-white/10 rounded-2xl p-3">
                    <Text className="text-white text-sm font-bold mb-2">통계 요약 ({chartType === 'ALL' ? '전체' : chartType === 'MAINTENANCE' ? '정비' : '주유'})</Text>
                    <View className="gap-1">
                        <View className="flex-row justify-between items-center py-1 border-b border-white/5">
                            <Text className="text-text-muted text-xs">평균 월 지출</Text>
                            <Text className="text-white text-xs font-bold">
                                {monthlyCostStats.avgMonthlyCost.toLocaleString()}원
                            </Text>
                        </View>
                        {monthlyCostStats.maxCostMonth && (
                            <View className="flex-row justify-between items-center py-1 border-b border-white/5">
                                <Text className="text-text-muted text-xs">최고 지출 월</Text>
                                <View className="flex-row items-baseline gap-1">
                                    <Text className="text-orange-500 text-[10px] font-semibold">
                                        {monthlyCostStats.maxCostMonth.monthLabel}
                                    </Text>
                                    <Text className="text-white text-xs font-bold">
                                        {(chartType === 'ALL' ? monthlyCostStats.maxCostMonth.totalCost :
                                            chartType === 'MAINTENANCE' ? monthlyCostStats.maxCostMonth.maintenanceCost :
                                                monthlyCostStats.maxCostMonth.fuelingCost).toLocaleString()}원
                                    </Text>
                                </View>
                            </View>
                        )}
                        <View className="flex-row justify-between items-center py-1">
                            <Text className="text-text-muted text-xs">
                                총 비용 ({monthlyCosts.length}개월)
                            </Text>
                            <Text className="text-primary text-sm font-bold">
                                {monthlyCostStats.totalCost.toLocaleString()}원
                            </Text>
                        </View>
                    </View>
                </View>

                {/* 간략한 상세 (Top 3) */}
                <View className="flex-1 bg-white/5 border border-white/10 rounded-2xl p-3">
                    <Text className="text-white text-sm font-bold mb-2">상세 내역 (Top 3)</Text>
                    {detailItems.length > 0 ? (
                        <View className="gap-1">
                            {detailItems.slice(0, 3).map((item) => (
                                <View key={item.id} className="flex-row justify-between items-center py-1 border-b border-white/5 last:border-0">
                                    <View className="flex-1 mr-1">
                                        <Text className={`text-xs truncate ${item.color === 'text-white' ? 'text-text-secondary' : item.color}`} numberOfLines={1}>
                                            {item.label}
                                        </Text>
                                    </View>
                                    <Text className="text-white text-xs font-bold">
                                        {(item.amount ?? 0).toLocaleString()}
                                    </Text>
                                </View>
                            ))}
                        </View>
                    ) : (
                        <View className="py-2 items-center">
                            <Text className="text-text-dim text-[10px]">내역이 없습니다.</Text>
                        </View>
                    )}
                </View>
            </View>
        </View>
    );
}
