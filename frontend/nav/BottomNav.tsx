import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { BottomTabBarProps } from '@react-navigation/bottom-tabs';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useUIStore } from '../store/useUIStore';

/**
 * 프로젝트 표준 하단 탭 바 (커스텀)
 * 기존의 Floating 디자인을 유지하면서 BottomTabNavigator와 연동됨
 */
export default function BottomNav({ state, descriptors, navigation }: BottomTabBarProps) {
    const bottomNavVisible = useUIStore(state => state.bottomNavVisible);
    const insets = useSafeAreaInsets();

    if (!bottomNavVisible) return null;

    return (
        <View
            className="w-full bg-surface-dark/95 backdrop-blur-xl border-t border-white/10 shadow-2xl"
            style={{ paddingBottom: insets.bottom }}
        >
            <View className="h-16 flex-row items-center justify-around px-2">
                {state.routes.map((route, index) => {
                    const { options } = descriptors[route.key];
                    const label =
                        options.tabBarLabel !== undefined
                            ? options.tabBarLabel
                            : options.title !== undefined
                                ? options.title
                                : route.name;

                    const isFocused = state.index === index;

                    const onPress = () => {
                        const event = navigation.emit({
                            type: 'tabPress',
                            target: route.key,
                            canPreventDefault: true,
                        });

                        if (!isFocused && !event.defaultPrevented) {
                            navigation.navigate(route.name);
                        }
                    };

                    // 아이콘 매핑 (이름 기준)
                    const getIcon = (name: string): keyof typeof MaterialIcons.glyphMap => {
                        switch (name) {
                            case 'MainHome': return 'home';
                            case 'DiagTab': return 'car-crash';
                            case 'HistoryTab': return 'history';
                            case 'SettingTab': return 'settings';
                            default: return 'help';
                        }
                    };

                    // 한글 라벨 매핑
                    const getLabel = (name: string) => {
                        switch (name) {
                            case 'MainHome': return '홈';
                            case 'DiagTab': return '진단';
                            case 'HistoryTab': return '기록';
                            case 'SettingTab': return '설정';
                            default: return name;
                        }
                    };

                    return (
                        <TouchableOpacity
                            key={route.key}
                            className="flex-1 items-center justify-center gap-1 h-full"
                            onPress={onPress}
                            activeOpacity={0.7}
                        >
                            <MaterialIcons
                                name={getIcon(route.name)}
                                size={24}
                                color={isFocused ? '#0d7ff2' : '#6b7280'}
                                style={isFocused ? { textShadowColor: 'rgba(13, 127, 242, 0.4)', textShadowRadius: 8 } : {}}
                            />
                            <Text className={`text-[10px] font-medium ${isFocused ? 'text-primary font-bold' : 'text-gray-500'}`}>
                                {getLabel(route.name)}
                            </Text>
                            {isFocused && (
                                <View className="absolute bottom-1 w-1 h-1 rounded-full bg-primary shadow-lg shadow-primary" />
                            )}
                        </TouchableOpacity>
                    );
                })}
            </View>
        </View>
    );
}
