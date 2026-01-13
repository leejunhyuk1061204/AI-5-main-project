import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';

import { useSafeAreaInsets } from 'react-native-safe-area-context';

export default function BottomNav() {
    const navigation = useNavigation<any>();
    const insets = useSafeAreaInsets();

    return (
        <View className="absolute left-6 right-6" style={{ bottom: (insets.bottom || 10) - 2 }}>
            <View className="rounded-2xl h-16 bg-[#0D0D0D]/90 backdrop-blur-xl border border-[#ffffff14] flex-row items-center justify-around shadow-2xl px-2">

                <TouchableOpacity
                    className="flex-1 items-center justify-center gap-1 h-full"
                    onPress={() => navigation.navigate('MainPage')}
                >
                    <MaterialIcons name="home" size={24} color="#0d7ff2" />
                    <Text className="text-[10px] font-bold text-primary">홈</Text>
                    {/* Active Indicator Glow */}
                    <View className="absolute bottom-1 w-1 h-1 rounded-full bg-primary shadow-lg shadow-primary" />
                </TouchableOpacity>

                <TouchableOpacity className="flex-1 items-center justify-center gap-1 h-full">
                    <MaterialIcons name="car-crash" size={24} color="#6b7280" />
                    <Text className="text-[10px] font-medium text-gray-500">진단</Text>
                </TouchableOpacity>

                <TouchableOpacity className="flex-1 items-center justify-center gap-1 h-full">
                    <MaterialIcons name="history" size={24} color="#6b7280" />
                    <Text className="text-[10px] font-medium text-gray-500">기록</Text>
                </TouchableOpacity>

                <TouchableOpacity className="flex-1 items-center justify-center gap-1 h-full">
                    <MaterialIcons name="settings" size={24} color="#6b7280" />
                    <Text className="text-[10px] font-medium text-gray-500">설정</Text>
                </TouchableOpacity>

            </View>
        </View>
    );
}
