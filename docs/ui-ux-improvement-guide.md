# UI/UX 개선 가이드 (Bottom Layout & Safe Area)

이 문서는 `PassiveReg.tsx`에서 적용된 하단 레이아웃 최적화 패턴을 프로젝트 전반에 일관되게 적용하기 위한 가이드라인입니다.

## 1. 개요
현재 프로젝트의 일부 페이지들이 최신 노치 기기(iPhone 등)의 하단 홈 바 영역(Safe Area)에 대응하지 않아, 버튼이 가려지거나 시각적 균형이 깨지는 이슈가 있습니다. 이를 해결하기 위해 표준화된 하단 레이아웃 패턴을 적용해야 합니다.

## 2. 주요 적용 패턴

### (1) 하단 고정 버튼 (Safe Area 대응)
하단에 고정된 버튼은 반드시 `useSafeAreaInsets`를 사용하여 기기별 하단 여백을 확보해야 합니다. 키보드가 올라올 때 버튼이 함께 올라오도록 `KeyboardController`와 연동합니다.

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
- **키보드 대응**: `react-native-keyboard-controller`를 사용하여 키보드 노출 시 높이를 동적으로 조절합니다.

## 6. 프론트엔드 아키텍처 전역 최적화 (핵심 과제)

현재 프론트엔드 코드는 각 페이지가 독립적으로 구현되어 중복 코드가 많고 기기 대응이 파편화되어 있습니다. 이를 근본적으로 해결하기 위한 5대 과제입니다.

### (1) 공통 레이아웃 컴포넌트 (`BaseScreen`) 도입
모든 페이지에서 `SafeAreaView`, `StatusBar`, `Header`, `BottomNav`를 수동으로 배치하지 않도록 표준 래퍼를 만듭니다.
- **요구사항**: `components/layout/BaseScreen.tsx`를 개발하고 모든 페이지에 적용할 것.
- **효과**: 전역 배경색, 상태바 스타일, 공통 패딩 처리를 한 곳에서 관리하여 코드 가사성을 높이고 전체 페이지의 톤앤매너를 일괄 제어함.

### (2) 하단 3중 레이어 및 네비게이션 시스템화
하단 영역을 물리적으로 고립된 3단계 층(Layer)으로 나누어 관리하여 기기 대응 및 키보드 간섭 이슈를 근본적으로 해결합니다.

- **4대 메인 페이지 고정**: `MainPage`, `DiagMain`, `HistoryMain`, `SettingMain` 4개 페이지를 제외한 서브 페이지에서는 하단 바를 노출하지 않음으로써 네비게이션 복잡도를 낮춤.
- **하단 3중 레이어 구성**:
    1.  **Layer 1 (Bottom Insets)**: iOS Home Bar, Android Gesture Bar 등을 위한 시스템 보호 영역.
    2.  **Layer 2 (Nav Bar)**: 4대 메뉴 전용 플로팅 네비게이션 바.
    3.  **Layer 3 (Keyboard/Dynamic UI)**: 키보드 활성화 시 올라오는 입력바 또는 하단 고정 요소들이 위치하는 동적 영역. (중앙 알림은 Zustand 모달 시스템으로 분리하여 관리)

### (3) 전역 상태 관리 (Zustand) 구축 및 전역 설정 통합
차량 정보, **중앙 알림(Central Alert)**, 그리고 기본적인 UI 상태(키보드 활성화 여부 등)를 전역 저장소에서 관리합니다.
- **요구사항**: 
    1. `store/useVehicleStore`: 선택된 차량 정보 전역 관리.
    2. `store/useAlertStore`: 화면 중앙에 뜨는 전역 알림 시스템. (사용자 선호 방식인 중앙 모달/알림창 형태)
    3. `store/useUIStore`: 키보드 활성화 여부 등 전역 UI 가시성 상태 관리 (예: 키보드 노출 시 하단 네비게이션 바 일괄 숨김).
- **효과**: 데이터 일관성 확보 및 불필요한 레이아웃 간섭 원천 차단.

### (4) 디자인 시스템 테마 정의 (`tailwind.config.js`)
프로젝트 전반에 사용되는 색상을 테마 컬러로 정의하여 하드코딩을 제거합니다.

### (5) 기기 파편화 대응 표준화
안드로이드 네비게이션 바 및 iOS Safe Area 대응을 전역 설정으로 박아 어느 기기에서나 동일한 몰입감을 제공합니다.

---

## 8. 레이아웃 전환 현황 (Migration Status)

현재 핵심 페이지를 중심으로 표준 아키텍처(`BaseScreen`)가 적용되었습니다. 나머지 서브페이지는 순차적으로 전환이 필요합니다.

| 분류 | 페이지명 | 상태 | 비고 |
| :--- | :--- | :--- | :--- |
| **메인(4대)** | `MainPage`, `DiagMain`, `HistoryMain`, `SettingMain` | **완료** | 표준 참조 모델 |
| **진단(서브)** | `AiProfessionalDiag` | **완료** | 서브페이지 참조 모델 |
| **진단(서브)** | `AiCompositeDiag`, `EngineSoundDiag`, `VisualDiagnosis` | 대기 | 전환 필요 |
| **설정(서브)** | `MyPage`, `CarManage`, `AlertSetting`, `Cloud`, `Membership` | 대기 | 전환 필요 |
| **인증(인증)** | `Login`, `SignUp`, `Tos`, `FindPW` | 대기 | 전환 필요 |
| **기타** | `Spec`, `SupManage`, `RecallHis`, `DrivingHis` | 대기 | 전환 필요 |

---

## 9. 단계별 개편 로드맵 (5단계)

대규모 공사로 인한 사이드 이펙트를 방지하기 위해 다음 순서로 작업을 진행합니다.

1. **[1단계] Zustand 기반 전역 상태 인프라 구축**: 패키지 설치, 차량/중앙 알림(Alert)/UI 상태 스토어 생성.
2. **[2단계] 표준 레이아웃(`BaseScreen`) 및 키보드 연동**: 페이지별 키보드-채팅창 연동 아키텍처 수립 및 래퍼 컴포넌트 적용.
3. **[3단계] 네비게이션 구조 전면 리팩토링**: `BottomTabNavigator` 도입 및 하단바 시스템화.
4. **[4단계] 디자인 토큰 및 테마 정규화**: 하드코딩 색상 전면 교체.
5. **[5단계] 최종 안정화 및 기기별 최적화**.
