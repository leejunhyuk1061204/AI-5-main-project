import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, Modal, Pressable, Platform } from 'react-native';
import { useDatePickerStore } from '../../store/useDatePickerStore';
import { MaterialIcons } from '@expo/vector-icons';
import {
    format,
    addMonths,
    subMonths,
    startOfMonth,
    endOfMonth,
    startOfWeek,
    endOfWeek,
    eachDayOfInterval,
    isSameMonth,
    isSameDay,
    isToday
} from 'date-fns';
import { ko } from 'date-fns/locale';

const GlobalDatePicker = () => {
    const { isVisible, initialDate, mode, onConfirm, closeDatePicker } = useDatePickerStore();
    const [currentMonth, setCurrentMonth] = useState(new Date());
    const [selectedDate, setSelectedDate] = useState(new Date());

    useEffect(() => {
        if (isVisible) {
            setCurrentMonth(initialDate || new Date());
            setSelectedDate(initialDate || new Date());
        }
    }, [isVisible, initialDate]);

    // 달력 데이터 생성
    const generateCalendarDays = () => {
        const monthStart = startOfMonth(currentMonth);
        const monthEnd = endOfMonth(monthStart);
        const startDate = startOfWeek(monthStart, { weekStartsOn: 0 }); // 일요일 시작
        const endDate = endOfWeek(monthEnd, { weekStartsOn: 0 });

        return eachDayOfInterval({ start: startDate, end: endDate });
    };

    const handlePrevMonth = () => setCurrentMonth(subMonths(currentMonth, 1));
    const handleNextMonth = () => setCurrentMonth(addMonths(currentMonth, 1));

    const handleDateSelect = (date: Date) => {
        setSelectedDate(date);
    };

    const handleConfirm = () => {
        if (onConfirm) {
            onConfirm(selectedDate);
        }
        closeDatePicker();
    };

    const weekDays = ['일', '월', '화', '수', '목', '금', '토'];
    const days = generateCalendarDays();

    if (!isVisible) return null;

    return (
        <Modal
            animationType="fade"
            transparent={true}
            visible={isVisible}
            onRequestClose={closeDatePicker}
            statusBarTranslucent={true}
        >
            <Pressable
                className="flex-1 bg-black/70 justify-center items-center px-6"
                onPress={closeDatePicker}
            >
                <Pressable
                    className="w-full bg-[#1A1F26] rounded-3xl overflow-hidden border border-white/10"
                    onPress={(e) => e.stopPropagation()}
                >
                    {/* Header: Month Navigation */}
                    <View className="flex-row items-center justify-between p-4 border-b border-white/5 bg-[#14181F]">
                        <Text className="text-lg font-bold text-white ml-2">
                            {format(currentMonth, 'yyyy년 M월', { locale: ko })}
                        </Text>
                        <View className="flex-row gap-1">
                            <TouchableOpacity
                                onPress={handlePrevMonth}
                                className="w-9 h-9 items-center justify-center rounded-full bg-white/5 active:bg-white/10"
                            >
                                <MaterialIcons name="chevron-left" size={24} color="#E2E8F0" />
                            </TouchableOpacity>
                            <TouchableOpacity
                                onPress={handleNextMonth}
                                className="w-9 h-9 items-center justify-center rounded-full bg-white/5 active:bg-white/10"
                            >
                                <MaterialIcons name="chevron-right" size={24} color="#E2E8F0" />
                            </TouchableOpacity>
                        </View>
                    </View>

                    <View className="p-4">
                        {/* Weekday Headers */}
                        <View className="flex-row justify-between mb-2">
                            {weekDays.map((day, index) => (
                                <View key={day} className="w-[13%] items-center justify-center py-2">
                                    <Text className={`text-xs font-bold ${index === 0 ? 'text-red-400' : 'text-slate-400'}`}>
                                        {day}
                                    </Text>
                                </View>
                            ))}
                        </View>

                        {/* Calendar Grid */}
                        <View className="flex-row flex-wrap justify-between">
                            {days.map((day, index) => {
                                const isSelected = isSameDay(day, selectedDate);
                                const isCurrentMonth = isSameMonth(day, currentMonth);
                                const isTodayDate = isToday(day);

                                return (
                                    <TouchableOpacity
                                        key={day.toISOString()}
                                        onPress={() => handleDateSelect(day)}
                                        className={`w-[13%] aspect-square items-center justify-center rounded-xl mb-1
                                            ${isSelected ? 'bg-primary shadow-lg shadow-blue-500/30' : ''}
                                            ${!isSelected && isTodayDate ? 'bg-white/5 border border-primary/30' : ''}
                                        `}
                                    >
                                        <Text
                                            className={`text-sm font-medium
                                                ${isSelected ? 'text-white font-bold' : ''}
                                                ${!isSelected && !isCurrentMonth ? 'text-slate-600' : ''}
                                                ${!isSelected && isCurrentMonth ? 'text-slate-200' : ''}
                                                ${!isSelected && isTodayDate ? 'text-primary' : ''}
                                            `}
                                        >
                                            {format(day, 'd')}
                                        </Text>
                                    </TouchableOpacity>
                                );
                            })}
                        </View>
                    </View>

                    {/* Footer Actions */}
                    <View className="p-4 pt-0 flex-row gap-3">
                        <TouchableOpacity
                            onPress={closeDatePicker}
                            className="flex-1 py-3.5 rounded-xl bg-white/5 items-center justify-center active:bg-white/10"
                        >
                            <Text className="text-slate-300 font-bold">취소</Text>
                        </TouchableOpacity>
                        <TouchableOpacity
                            onPress={handleConfirm}
                            className="flex-1 py-3.5 rounded-xl bg-primary items-center justify-center shadow-lg shadow-blue-500/20 active:bg-blue-600"
                        >
                            <Text className="text-white font-bold">확인</Text>
                        </TouchableOpacity>
                    </View>
                </Pressable>
            </Pressable>
        </Modal>
    );
};

export default GlobalDatePicker;
