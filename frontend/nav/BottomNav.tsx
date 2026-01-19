import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';

import { useSafeAreaInsets } from 'react-native-safe-area-context';

export default function BottomNav() {
    const navigation = useNavigation<any>();
    const route = useRoute();
    const insets = useSafeAreaInsets();

    const isActive = (routeName: string) => route.name === routeName;

    const NavItem = ({ name, label, icon, target }: { name: string, label: string, icon: keyof typeof MaterialIcons.glyphMap, target?: string }) => {
        const active = isActive(name);
        return (
            <TouchableOpacity
                className="flex-1 items-center justify-center gap-1 h-full"
                onPress={() => target && navigation.navigate(target)}
                activeOpacity={0.7}
            >
                <MaterialIcons
                    name={icon}
                    size={24}
                    color={active ? '#0d7ff2' : '#6b7280'}
                    style={active ? { textShadowColor: 'rgba(13, 127, 242, 0.4)', textShadowRadius: 8 } : {}}
                />
                <Text
                    className={`text-[10px] font-medium ${active ? 'text-primary font-bold' : 'text-gray-500'}`}
                >
                    {label}
                </Text>
                {active && (
                    <View className="absolute bottom-1 w-1 h-1 rounded-full bg-primary shadow-lg shadow-primary" />
                )}
            </TouchableOpacity>
        );
    };

    return (
        <View className="absolute left-6 right-6 z-50" style={{ bottom: (insets.bottom || 10) - 2 }}>
            <View className="rounded-2xl h-16 bg-[#161d27]/95 backdrop-blur-xl border border-[#ffffff14] flex-row items-center justify-around shadow-2xl px-2">
                <NavItem name="MainPage" label="홈" icon="home" target="MainPage" />
                <NavItem name="DiagMain" label="진단" icon="car-crash" target="DiagMain" />
                <NavItem name="HistoryMain" label="기록" icon="history" target="HistoryMain" />
                <NavItem name="SettingMain" label="설정" icon="settings" target="SettingMain" />
            </View>
        </View>
    );
}
