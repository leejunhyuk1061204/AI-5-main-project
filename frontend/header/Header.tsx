import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation, useFocusEffect } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';

export default function Header() {
    const navigation = useNavigation<any>();
    const [nickname, setNickname] = React.useState<string | null>(null);

    useFocusEffect(
        React.useCallback(() => {
            const checkLoginStatus = async () => {
                const storedNickname = await AsyncStorage.getItem('userNickname');
                setNickname(storedNickname);
            };
            checkLoginStatus();
        }, [])
    );

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
                <Text className="text-gray-400 text-xs mt-1">
                    Vehicle Status: Connected
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
