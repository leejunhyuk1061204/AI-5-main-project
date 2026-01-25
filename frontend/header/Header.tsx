import React, { useEffect } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { useUserStore } from '../store/useUserStore';
import { useBleStore } from '../store/useBleStore';

export default function Header() {
    const navigation = useNavigation<any>();
    const { nickname, loadUser } = useUserStore();
    const { status } = useBleStore();

    useEffect(() => {
        loadUser();
    }, []);

    // 블루투스 상태에 따른 텍스트 및 색상 설정
    const getStatusInfo = () => {
        switch (status) {
            case 'connected':
                return { text: 'Connected', color: 'text-success' };
            case 'connecting':
                return { text: 'Connecting...', color: 'text-warning' };
            default:
                return { text: 'Disconnected', color: 'text-gray-400' };
        }
    };

    const statusInfo = getStatusInfo();

    return (
        <View className="flex-row items-center justify-between px-6 py-4 pb-2 bg-transparent z-10">
            <View>
                {nickname ? (
                    <Text className="text-2xl font-bold text-primary tracking-tight">
                        {nickname}님
                    </Text>
                ) : (
                    <TouchableOpacity onPress={() => navigation.navigate('Login')}>
                        <Text className="text-2xl font-bold text-primary tracking-tight">
                            로그인
                        </Text>
                    </TouchableOpacity>
                )}
                <Text className={`text-xs mt-1 font-medium ${statusInfo.color}`}>
                    Vehicle Status: {statusInfo.text}
                </Text>
            </View>
            <TouchableOpacity
                className="w-10 h-10 items-center justify-center rounded-full bg-[#1b2127] border border-white/10 active:scale-95"
                activeOpacity={0.7}
                onPress={() => navigation.navigate('AlertMain')}
            >
                <MaterialIcons name="notifications-none" size={24} color="white" />
            </TouchableOpacity>
        </View>
    );
}
