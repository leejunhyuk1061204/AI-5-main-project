# UI/UX 개선 가이드 (Bottom Layout & Safe Area)

이 문서는 `PassiveReg.tsx`에서 적용된 하단 레이아웃 최적화 패턴을 프로젝트 전반에 일관되게 적용하기 위한 가이드라인입니다.

## 1. 개요
현재 프로젝트의 일부 페이지들이 최신 노치 기기(iPhone 등)의 하단 홈 바 영역(Safe Area)에 대응하지 않아, 버튼이 가려지거나 시각적 균형이 깨지는 이슈가 있습니다. 이를 해결하기 위해 표준화된 하단 레이아웃 패턴을 적용해야 합니다.

## 2. 주요 적용 패턴

### (1) 하단 고정 버튼 (Safe Area 대응)
하단에 고정된 버튼은 반드시 `useSafeAreaInsets`를 사용하여 기기별 하단 여백을 확보해야 합니다.

```tsx
const insets = useSafeAreaInsets();

return (
  <View 
    className="absolute bottom-0 left-0 right-0 p-5 bg-background-dark/80 backdrop-blur-md" 
    style={{ paddingBottom: insets.bottom + 10 }}
  >
    <TouchableOpacity className="w-full h-14 bg-primary rounded-xl">
      <Text>등록 완료</Text>
    </TouchableOpacity>
  </View>
);
```

### (2) 스크롤 뷰 여백 최적화
스크롤 가능한 콘텐츠가 하단 고정 바나 네비게이션 바에 가려지지 않도록 `contentContainerStyle`에 동적 여백을 추가합니다.

```tsx
<ScrollView 
  contentContainerStyle={{ paddingBottom: insets.bottom + 100 }}
>
  {/* 콘텐츠 */}
</ScrollView>
```

### (3) 하단 슬라이드 모달 (Bottom Sheet)
중앙 팝업 방식보다 하단에서 슬라이드되는 방식이 모바일 사용자 경험에서 더 선호됩니다.

- **디자인 요소**: `rounded-t-[32px]`, `backdrop-blur-sm` 배경, 하단 `insets.bottom` 적용.
- **키보드 대응**: 입력 필드가 있는 경우 `KeyboardAvoidingView`와 연동하여 키보드 노출 시 높이 동적 조절.

## 3. 우선 적용 권장 페이지
- **BottomNav.tsx**: 플로팅 바의 하단 여백(`bottom`)을 `insets.bottom` 기반으로 미세 조정.
- **MainPage.tsx**: 스크롤 하단 여백이 현재 하드코딩 되어 있으므로 유연하게 변경.
- **ActiveReg.tsx**: 하단 "장치 검색 및 연결" 버튼 영역 스타일 고도화.
- **ObdConnect.tsx**: 모달 레이아웃의 Safe Area 대응.

## 4. 구현 참고
- **PassiveReg.tsx**: `StatusModal`을 활용한 세련된 알림 및 Safe Area 대응 버튼의 표준 예시입니다.
- **CarManage.tsx**: 중앙 팝업 형식을 유지하면서도 스크롤 하단 여백(`paddingBottom`)을 최적화한 예시입니다.
