import React, { useEffect } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { useUserStore } from '../store/useUserStore';
import { useBleStore } from '../store/useBleStore';

interface HeaderProps {
    navigation?: any;
    title?: string;
}

export default function Header({ navigation: propNavigation, ...props }: HeaderProps) {
    const navigation = propNavigation || useNavigation<any>();
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
                {props.title ? (
                    <Text className="text-2xl font-bold text-white tracking-tight">
                        {props.title}
                    </Text>
                ) : nickname ? (
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
                className="relative w-11 h-11 items-center justify-center rounded-xl bg-white/5 border border-white/10 active:bg-white/10"
                activeOpacity={0.7}
                onPress={() => navigation.navigate('AlertMain')}
            >
                <MaterialIcons name="notifications-none" size={22} color="#0d7ff2" />
                {/* Unread Badge - 읽지 않은 알림이 있을 때 표시 */}
                {/* <View className="absolute top-1.5 right-1.5 w-2 h-2 bg-error rounded-full border border-[#101922]" /> */}
            </TouchableOpacity>
        </View>
    );
}
