// 헤더 '온톨로지란?' 버튼이 여는 전체화면 설명 페이지(모달 아님 — 콘텐츠가 많아 페이지로).
// 교재(2026 마이크로디그리 – 빅데이터 분석, 이채석/KAIST)의 그래프DB·온톨로지·LLM 연계 강의를
// 이 앱 맥락으로 쉽게 재구성하고, 팔란티어 온톨로지·디지털 트윈 공개자료로 심화했다.
// 순수 프론트(과금 없음). App이 content 영역에서 이 페이지를 조건부 렌더한다.
import { useEffect, useRef } from "react";

// 인라인 코드 예시(괄호/중괄호가 있어 JSX 텍스트로 두면 파싱됨 → 문자열로 렌더).
function Code({ children }: { children: string }) {
  return <code className="guide-code">{children}</code>;
}

export default function OntologyGuide({ onBack }: { onBack: () => void }) {
  const backRef = useRef<HTMLButtonElement>(null);
  const onBackRef = useRef(onBack);
  onBackRef.current = onBack;

  // 페이지 진입 시 최상단으로 + 돌아가기 버튼 포커스(스크린리더 전환 인지). Esc로 돌아가기.
  useEffect(() => {
    window.scrollTo(0, 0);
    backRef.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onBackRef.current();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="guide-page">
      <div className="guide-page-bar">
        <button type="button" ref={backRef} className="guide-back" onClick={onBack}>
          ← 돌아가기
        </button>
      </div>

      <article className="guide-article" aria-labelledby="guide-title">
        <header className="guide-hero">
          <div className="guide-eyebrow">지식그래프 빌더 안내</div>
          <h1 id="guide-title" className="guide-hero-title">
            온톨로지란 무엇이고, 왜 필요한가
          </h1>
          <p className="guide-lead">
            이 앱이 왜 만들어졌고, 여러분이 문장 하나를 입력할 때 실제로 무슨 일이 일어나는지, 그리고
            이 기술이 왜 세계적 기업의 핵심 자산이자 <b>진짜 디지털 트윈</b>의 뼈대인지까지 —
            온톨로지 이론은 몰라도 됩니다.
          </p>
        </header>

        {/* 1 */}
        <section className="guide-sec">
          <div className="guide-num">1</div>
          <h3 className="guide-h">왜 ‘그래프’인가 — 조인 지옥에서 벗어나기</h3>
          <p className="guide-p">
            같은 데이터라도 <b>저장 구조가 다르면 답을 얻는 비용</b>이 달라집니다. 우리가 흔히 쓰는
            표(관계형 DB)는 이름과 달리 <b>관계를 직접 저장하지 않습니다.</b> 표끼리는 ‘외래키(참조값)’만
            갖고, 실제 연결은 질문할 때마다 <b>JOIN(조인)으로 매번 다시 계산</b>합니다.
          </p>
          <p className="guide-p">
            연결을 한 단계 따라갈 때마다 조인이 한 줄씩 늘어납니다. 더 큰 문제는{" "}
            <b>“몇 단계를 따라가야 하는지 미리 알아야” 쿼리를 쓸 수 있다</b>는 점입니다.
          </p>
          <div className="guide-example">
            <span className="guide-example-tag">현장 질문</span>
            “이 관로가 파손되면 물이 끊기는 수용가는?” — 몇 단계 떨어져 있는지 사람이 미리 알 수 없습니다.
          </div>
          <p className="guide-p">
            그래프는 각 <b>노드(점)가 이웃으로 가는 길을 직접 저장</b>합니다. 그래서 “닿을 때까지
            따라가라”가 기본 동작이고, 탐색 비용은 전체 데이터 크기가 아니라 <b>경로 길이에만 비례</b>합니다.
          </p>
          <div className="guide-callout">
            한 줄 정리 — <b>관계를 계산하지 말고, 아예 저장하자.</b>
          </div>
          <p className="guide-p guide-muted">
            판별 팁: “~에 연결된 / ~를 거쳐 / ~까지의 경로” 같은 <b>연결 추적</b> 질문이면 그래프가,
            “합계·평균·상위 N” 같은 <b>집계</b> 질문이면 기존 표가 맞습니다. 실무는 둘을 섞어 씁니다.
          </p>
        </section>

        {/* 2 */}
        <section className="guide-sec">
          <div className="guide-num">2</div>
          <h3 className="guide-h">그래프의 부품은 딱 4가지</h3>
          <p className="guide-p">
            <b>노드 · 레이블(유형) · 관계(방향+유형) · 속성</b> 네 가지면 지식을 거의 다 표현할 수 있습니다.
          </p>
          <ul className="guide-list">
            <li>
              <b>노드</b> — 개체 하나 (녹조, 남조류, 조류경보제…)
            </li>
            <li>
              <b>레이블</b> — 그 노드의 유형 꼬리표 (<Code>:현상</Code>, <Code>:생물</Code>,{" "}
              <Code>:제도</Code>)
            </li>
            <li>
              <b>관계</b> — 반드시 <b>방향</b>과 <b>유형</b>을 가짐. 흐름·인과가 있는 도메인에서는 방향이
              핵심 정보입니다.
            </li>
            <li>
              <b>속성</b> — 노드·관계에 붙는 키-값 (남조류세포수 ≥ 1,000 cells/mL)
            </li>
          </ul>
          <div className="guide-example">
            <span className="guide-example-tag">녹조 예</span>
            <Code>{"(녹조:현상) -[원인]-> (남조류:생물)"}</Code>
          </div>
          <div className="guide-example">
            <span className="guide-example-tag">급수계통 예(교재)</span>
            <Code>{"(정수장:Plant) -[:FEEDS {설계용량:20000}]-> (배수지:Reservoir)"}</Code>
          </div>
        </section>

        {/* 3 */}
        <section className="guide-sec">
          <div className="guide-num">3</div>
          <h3 className="guide-h">그래프DB · 지식그래프 · 온톨로지 — 그릇 / 요리 / 레시피</h3>
          <p className="guide-p">세 단어가 자주 헷갈립니다. 요리에 비유하면 단번에 정리됩니다.</p>
          <ul className="guide-list">
            <li>
              <b>그래프DB = 그릇</b> · 노드·관계·속성을 담는 <b>저장 기술</b>.
            </li>
            <li>
              <b>지식그래프 = 요리</b> · 그 그릇에 담긴, ‘합의된 의미로 연결된’ <b>조직의 지식 자산</b>.
              사람과 기계가 함께 읽는 지식 지도.
            </li>
            <li>
              <b>온톨로지 = 레시피·용어 사전</b> · “‘조류경보제’란 무엇이고, ‘단계’라는 관계는 정확히 무슨
              뜻인가”를 정해 둔 약속.
            </li>
          </ul>
          <p className="guide-p guide-muted">
            위로 갈수록 ‘기술’이 아니라 ‘자산’입니다. 구글이 2012년{" "}
            <b>“things, not strings(문자열이 아니라 사물)”</b>라며 검색에 지식그래프를 붙인 게 대표 사례.
          </p>
        </section>

        {/* 4 */}
        <section className="guide-sec">
          <div className="guide-num">4</div>
          <h3 className="guide-h">온톨로지란 무엇인가</h3>
          <p className="guide-p">
            어원은 철학의 <b>존재론(ontology)</b> — “세상에 무엇이 존재하고, 서로 어떤 관계인가.”
            정보과학은 이걸 빌려와, 어떤 분야의 <b>개념(사물의 유형)과 관계를 컴퓨터가 읽을 수 있는
            형태로 적어 둔 명세</b>로 씁니다.
          </p>
          <div className="guide-quote">
            “공유된 개념화의 명시적 명세” <span className="guide-cite">— Gruber, 1993</span>
          </div>
          <ul className="guide-list">
            <li>
              <b>공유된</b> — 나 혼자가 아니라 <b>조직이 합의한</b>
            </li>
            <li>
              <b>개념화</b> — 세계를 개념으로 정리한
            </li>
            <li>
              <b>명시적 명세</b> — 머릿속이 아니라 <b>문서·코드로 또박또박 적은</b>
            </li>
          </ul>
          <p className="guide-p">
            구성요소는 5가지: <b>클래스(개념) · 속성 · 관계 · 계층(상하위) · 제약</b>. 일상의 닮은꼴로 보면{" "}
            <b>분류체계 + 조직도 + 용어집</b>을 하나로 합쳐 ‘기계가 읽게’ 만든 것입니다.
          </p>
        </section>

        {/* 5 */}
        <section className="guide-sec">
          <div className="guide-num">5</div>
          <h3 className="guide-h">온톨로지는 왜 강력한가 — 공리와 추론, 그리고 용어 통일</h3>
          <p className="guide-p">
            진짜 힘은 <b>적어 두면 기계가 대신 결론을 내는</b> 데 있습니다. ‘참이라고 선언한 규칙(공리)’을
            적어 두면, <b>아무도 입력하지 않은 사실</b>도 자동으로 도출됩니다(추론).
          </p>
          <div className="guide-example">
            <span className="guide-example-tag">추론 예</span>
            “정수장 ⊂ 시설”, “모든 시설은 정기점검 대상” → 기계는 <b>“정수장은 정기점검 대상”</b>이라고
            스스로 결론냅니다(그렇게 입력한 적이 없어도).
          </div>
          <p className="guide-p">
            관계에 성질(<b>전이·대칭·역</b>)을 선언하면 그만큼 기계가 대신 추론합니다. 예를 들어 ‘연결’이
            전이적이면 A–B, B–C가 있을 때 A는 C에 도달합니다 — 앞서 본 “닿을 때까지 따라가라”가 곧 전이
            추론입니다.
          </p>
          <p className="guide-p">
            <b>용어 통일</b>도 핵심입니다. 같은 것을 부서마다 다르게 부르면 지식이 흩어집니다. 온톨로지는
            ‘블록’=‘DMA’처럼 <b>별칭을 하나의 표준어로 묶습니다.</b>{" "}
            <span className="guide-muted">(이 앱의 ‘표준 어휘 정규화’가 바로 이 역할입니다.)</span>
          </p>
          <div className="guide-callout">
            <b>스키마 vs 온톨로지</b> — 스키마는 <b>형식</b>(“이 칸은 숫자다”), 온톨로지는 <b>개념</b>
            (“정수장이란 무엇이고 무엇과 어떤 관계를 맺을 수 있는가”).
          </div>
          <p className="guide-p guide-muted">
            바닥부터 만들 필요는 없습니다. 물 분야엔 국제 표준 온톨로지(ETSI <b>SAREF4WATR</b> 등)가 이미
            있어, 백지 설계보다 <b>확장해 쓰는 편이 빠르고 어긋남도 적습니다.</b>
          </p>
        </section>

        {/* 6 */}
        <section className="guide-sec">
          <div className="guide-num">6</div>
          <h3 className="guide-h">어떻게 설계하나 — 질문에서 출발한다</h3>
          <p className="guide-p">
            온톨로지 설계는 복잡한 규칙이 아니라 <b>‘답하고 싶은 질문’에서 출발</b>합니다. 방법이 놀랄
            만큼 단순합니다 — 질문 문장에서 <b>명사에 동그라미, 동사에 밑줄.</b> 명사는 노드, 동사는
            관계가 됩니다.
          </p>
          <div className="guide-example">
            <span className="guide-example-tag">분해 예</span>
            “<u>조류경보제</u>는 <u>관심·경계·대발생</u> 3<b>단계로 운영</b>된다” → 명사(노드):
            조류경보제·관심·경계·대발생 / 동사(관계): 단계
          </div>
          <p className="guide-p">
            이 질문 목록이 곧 <b>범위이자 성공 기준</b>입니다(전부 답할 수 있으면 합격). 백과사전을 만들
            필요 없이 <b>질문이 요구하는 만큼만</b> 만들면 됩니다.
          </p>
          <div className="guide-callout">
            바로 이게 여러분이 이 앱에서 <b>문장을 입력할 때 하는 일</b>입니다 — 어렵게 느껴지던
            ‘모델링’이 사실은 <b>문장 쓰기</b>입니다.
          </div>
        </section>

        {/* 7 */}
        <section className="guide-sec">
          <div className="guide-num">7</div>
          <h3 className="guide-h">그럼 AI(LLM)는 — 환각, 그리고 GraphRAG</h3>
          <p className="guide-p">
            챗봇 같은 LLM은 ‘사실을 조회하는 기계’가 아니라 <b>‘그럴듯한 다음 말을 고르는 기계’</b>입니다.
            그래서 <b>확신에 차서 틀린 답(환각)</b>을 만들 수 있습니다 — 물·안전 분야에선 치명적이죠.
          </p>
          <p className="guide-p">
            해법은 “LLM을 쓰지 않기”가 아니라 <b>“LLM에 기억을 맡기지 않기”</b>입니다.
          </p>
          <ul className="guide-list">
            <li>
              <b>저장·조회(사실)</b>는 → <b>그래프</b>가
            </li>
            <li>
              <b>이해·표현(말)</b>은 → <b>LLM</b>이
            </li>
          </ul>
          <p className="guide-p">
            이 구조를 <b>GraphRAG / Text2Cypher</b>라 부르고, 설계 철학은{" "}
            <b>“그래프가 먼저, LLM은 마지막(graph-first, LLM-last)”</b>입니다. 덕분에 ① 모든 답이 특정
            노드를 가리키고(근거 추적), ② 없으면 “확인되지 않음”이라 말하며(정직한 실패), ③ 잘못된 번역조차
            거짓 사실이 아니라 <b>검증 가능한 오타</b>로 드러납니다. 판정자는 LLM이 아니라 그래프입니다.
          </p>
          <p className="guide-p guide-muted">
            그리고 <b>좋은 온톨로지일수록 번역(질문→쿼리)이 정확</b>해집니다.
          </p>
        </section>

        {/* 심화 구분선 */}
        <div className="guide-divider" role="separator" aria-label="심화 섹션 시작">
          <span>심화 · 더 깊이 — 왜 ‘사업’이 되고, ‘진짜 디지털 트윈’의 핵심인가</span>
        </div>

        {/* 8 — 팔란티어 (심화·확장) */}
        <section className="guide-sec">
          <div className="guide-num">8</div>
          <h3 className="guide-h">온톨로지는 어떻게 ‘사업’이 되나 — 팔란티어 심층</h3>
          <p className="guide-p">
            온톨로지가 추상적 이론처럼 보여도, 시가총액 수천억 달러의 데이터 기업{" "}
            <b>팔란티어(Palantir)</b>의 <b>핵심 자산이자 사업 모델</b>이 바로 이것입니다. 팔란티어는
            제품군(AIP·Foundry·Apollo)을 묶어 <b>‘기업용 운영체제(operating system)’</b>를 표방하는데,
            그 <b>심장이 온톨로지</b>입니다. 온톨로지는 흩어진 시스템의{" "}
            <b>데이터·로직·행동·보안 정책을, 사람과 AI가 함께 다룰 수 있는 하나의 표현</b>으로 통합하고,
            팔란티어는 이를 <b>“조직의 디지털 트윈(a digital twin of the organization)”</b>이라 부릅니다.
          </p>
          <div className="guide-quote">
            “온톨로지는 <b>데이터가 아니라</b> 기업의 복잡하게 얽힌 <b>‘의사결정’</b>을 표현하도록 설계됐다 —
            사람과 AI가 <b>물리세계와 맞물려 돌아가는 업무</b>를 함께 수행하도록.”
            <span className="guide-cite">— Palantir 온톨로지 개요(번역·요지)</span>
          </div>

          <h4 className="guide-h4">① 구조: 명사(의미) + 동사(행동)</h4>
          <ul className="guide-list">
            <li>
              <b>의미(semantic) = 명사</b> · 객체·속성·관계 — <b>이 앱이 만드는 바로 그 층</b>.
            </li>
            <li>
              <b>동역학(kinetic) = 동사</b> · 액션·함수 — “재고를 재배정하라”, “밸브를 잠가라”처럼 현실에
              개입하는 <b>통제된 행동</b>. 팔란티어 왈 <b>“의미는 반드시 동역학과 짝지어야 한다.”</b>
            </li>
          </ul>

          <h4 className="guide-h4">② AI를 붙이는 법: RAG를 넘어 OAG</h4>
          <p className="guide-p">
            LLM을 혼자 두면 그럴듯한 환각을 냅니다. 팔란티어는 LLM을 온톨로지에 묶어 <b>“데이터를 넘어
            로직과 행동까지”</b> 확장하며, 이를 <b>RAG를 넘어선 OAG(Ontology-Augmented Generation)</b>라
            부릅니다. AIP 에이전트는 <b>원시 테이블이 아니라 ‘객체 타입’을 조회</b>하고,{" "}
            <b>임의 행동이 아니라 ‘통제된 액션’만</b> 호출합니다.
          </p>
          <div className="guide-callout">
            온톨로지에 묶인 AI가 환각을 못 내는 이유는 간단합니다 — <b>살아있는 ‘주문’ 객체를 직접 조회하는
            AI는 존재하지 않는 주문번호를 지어낼 수 없습니다.</b> 게다가 <b>사람과 AI에 똑같은
            보안·거버넌스</b>가 적용되고, 실제 실행은 <b>사람이 최종 승인</b>합니다.
          </div>

          <h4 className="guide-h4">③ 한 컷 사례: 공급망 ‘Disruption Bot’</h4>
          <p className="guide-p">
            흩어진 ERP·MES·CRM을 <b>공통 객체(공장·생산라인·주문…)</b>로 묶어 두면, 공급 차질이 났을 때
            AI가 온톨로지를 따라 영향을 추론해 <b>새로운 재배분 계획을 제시</b>합니다 → 사람이 검토·승인 →{" "}
            <b>통제된 액션</b>으로 여러 부서에 걸쳐 실행. 데이터가 곧바로 <b>의사결정과 행동</b>이 되는 흐름입니다.
          </p>

          <h4 className="guide-h4">④ 왜 ‘사업’이 되나 (해자·moat)</h4>
          <ol className="guide-steps">
            <li>
              <b>재사용의 복리</b> — 한 번 조직을 온톨로지로 모델링하면, 새 앱·분석·AI가 매번 데이터를
              재해석하지 않고 <b>같은 의미 층을 공유</b>합니다. 쓸수록 가치가 쌓입니다.
            </li>
            <li>
              <b>전환비용</b> — 조직의 ‘운영 모델’ 자체가 온톨로지에 담기니 갈아타기 어렵습니다.
            </li>
            <li>
              <b>AI 시대의 필수 접점</b> — AI가 안전하게 행동하려면 반드시 이 의미·행동 층이 필요합니다.
              그래서 <b>일부에서는</b> 온톨로지를 두고 <b>‘엔터프라이즈 AI의 운영체제’</b>라고도 부릅니다.
            </li>
          </ol>
          <div className="guide-callout">
            한 줄 — <b>데이터를 ‘의미·관계·행동’으로 바꾼 조직만이</b> AI를 안전하게, 반복 가능하게 굴릴 수
            있습니다. 그 층 자체가 자산이자 해자입니다.
          </div>
        </section>

        {/* 9 — 디지털 트윈 가설 검토 */}
        <section className="guide-sec">
          <div className="guide-num">9</div>
          <h3 className="guide-h">그래서 ‘진짜’ 디지털 트윈이란 — 관계기반 추론</h3>
          <div className="guide-example">
            <span className="guide-example-tag">검토할 생각</span>
            “진정한 의미의 디지털 트윈은 <b>물리세계를 이해하는 것</b> + <b>관계기반의 추론</b>이다.”
          </div>
          <div className="guide-callout guide-callout-final">
            <b>검토 결과 — 맞습니다. 핵심을 정확히 짚었습니다.</b>
          </div>
          <p className="guide-p">
            흔히 ‘디지털 트윈’이라 불리는 많은 것은 사실 <b>3D 시각화 + 센서 수치 대시보드</b>에 그칩니다.
            보기엔 그럴듯하지만, “이 관로가 터지면 어디가 단수되나?”, “이 사고의 원인은?”에는 답하지
            못합니다 — 그건 <b>관계를 따라가는 추론</b>이라야 나오는 답이기 때문입니다(교재의 단수 영향
            분석이 정확히 이것).
          </p>
          <p className="guide-p">
            학계도 같은 방향입니다. 기하(3D)·센서만으론 부족하고, <b>온톨로지·지식그래프로 의미와 관계를
            얹어 추론</b>하는 <b>‘인지형(cognitive)·의미형(semantic) 디지털 트윈’</b>이 다음 단계로 꼽힙니다.
            팔란티어가 <b>물리적 형체가 없는 ‘조직’</b>에도 디지털 트윈을 말할 수 있는 이유가 바로 이것 —
            트윈의 본질은 3D 모형이 아니라 <b>객체+관계+행동의 의미 모델</b>이기 때문입니다.
          </p>
          <p className="guide-p">다만 두 가지를 더하면 <b>더 정확</b>해집니다(다듬기).</p>
          <ul className="guide-list">
            <li>
              ‘물리세계 이해’는 정지된 구조만이 아니라 <b>살아있는 상태(실시간 센서)와 거동(시뮬레이션)</b>
              까지 포함해야 합니다. 관계 모델과 실시간 상태가 만나야 ‘지금’의 추론이 됩니다.
            </li>
            <li>
              추론에서 끝나지 않고 <b>다시 세계로 개입(행동)</b>할 때 고리가 닫힙니다. 이게 팔란티어의
              ‘동역학(kinetic)’이자, 성숙한 트윈이 지향하는 지점입니다.
            </li>
          </ul>
          <div className="guide-callout">
            다듬은 정리 — <b>진짜 디지털 트윈 = ① 실시간 상태(센서) + ② 의미·관계(온톨로지/지식그래프) + ③
            그 위의 추론·시뮬레이션 + ④ 다시 현실로의 행동.</b> 당신의 문장은 이 중 <b>이해(①②)와
            추론(③)</b>을 관통하는 가장 중요한 통찰을 담고 있습니다.
          </div>
        </section>

        {/* 10 — 수자원 디지털 트윈 확장(구체 시나리오) */}
        <section className="guide-sec">
          <div className="guide-num">10</div>
          <h3 className="guide-h">이 앱 → K-water ‘녹조·수자원 디지털 트윈’으로</h3>
          <p className="guide-p">
            위의 네 개 층으로 이 앱을 확장하면 어떤 모습일까요? <b>녹조 관리</b>로 구체화해 봅니다.
          </p>

          <h4 className="guide-h4">지금 이 앱이 만드는 것 = ② 의미·관계 층</h4>
          <div className="guide-example">
            <Code>{"(녹조:현상)-[원인]->(남조류:생물)"}</Code>{" · "}
            <Code>{"(조류경보제:제도)-[단계]->(경계:경보단계)"}</Code>
            <br />
            <Code>{"(경계)-[기준지표]->(남조류세포수:지표 {value:10000,unit:'cells/mL'})"}</Code>{" · "}
            <Code>{"(대청호:저수지)-[측정]->(A지점:측정소)"}</Code>
          </div>
          <p className="guide-p guide-muted">
            <b>참고</b>: 이 앱은 이미 노드에 <b>정량 속성(값·단위·관측시각)</b>을 저장합니다 — 아래 ‘①
            실시간 상태’ 층의 씨앗이 이미 심겨 있는 셈입니다.
          </p>

          <h4 className="guide-h4">여기에 세 층을 얹으면</h4>
          <ul className="guide-list">
            <li>
              <b>① 실시간 상태(센서)</b> — 측정소 노드에 실측값을 흘려 넣음: 남조류세포수·클로로필-a·
              수온·용존산소(DO)·pH·취수량·방류량.
            </li>
            <li>
              <b>③ 추론·시뮬레이션</b> — 관계를 따라가는 질문에 답:
              <ul className="guide-sublist">
                <li>
                  <b>영향 전파</b>: “대청호 상류 측정소가 <b>‘경계’(≥10,000)</b>를 넘으면 영향받는
                  취수장·정수장·수용가는?” → <Code>{"(측정소)-(저수지)-(취수장)-(정수장)-(수용가)"}</Code>{" "}
                  경로 전이 추론.
                </li>
                <li>
                  <b>원인 추적</b>: 수온↑·영양염류↑ → 남조류 증식 → 녹조 (원인 관계 역추적).
                </li>
                <li>
                  <b>규칙 발동</b>: 관측값이 기준지표를 넘으면 → 연결된 <b>경보단계</b> → <b>대응조치</b>가
                  자동 후보로.
                </li>
              </ul>
            </li>
            <li>
              <b>④ 행동(kinetic)</b> — 대응조치를 실제 개입으로: 취수구 심도 조정, 조류제거선·살수장치
              가동, 정수장 분말활성탄 주입 증대, 조류경보 발령 통지. 실행은 <b>담당자 승인 후</b>(팔란티어의
              ‘동사’와 같은 자리).
            </li>
          </ul>

          <div className="guide-scenario">
            <div className="guide-scenario-title">한 컷 시나리오</div>
            <ol className="guide-steps">
              <li>대청호 A지점 <b>남조류세포수 12,000 cells/mL</b> 관측(① 센서).</li>
              <li>
                트윈이 ③으로 <b>‘경계’ 판정</b> + 하류 <b>3개 취수장·1개 정수장 영향</b> 식별 + 과거
                유사사례 근거 제시.
              </li>
              <li>
                ④로 <b>대응조치 후보</b> 제시(취수구 하향, 활성탄 증량) → <b>담당자 승인·실행</b>.
              </li>
              <li>실행 결과가 다시 ①로 <b>피드백</b> — 고리가 닫힘.</li>
            </ol>
          </div>
          <div className="guide-callout guide-callout-final">
            이 앱은 그 트윈의 <b>뇌(의미·관계·추론)</b>를 짓습니다. 센서·행동 연동은 그 위에 얹으면 됩니다 —
            <b> K-water가 표준을 ‘쓰는 조직’에서 ‘만드는 조직’으로</b> 가는 길목입니다.
          </div>
        </section>

        {/* ▶ 마무리 */}
        <section className="guide-sec guide-sec-final">
          <div className="guide-num">▶</div>
          <h3 className="guide-h">그래서, 이 앱에서 여러분이 하는 일</h3>
          <p className="guide-p">
            이 앱은 위의 <b>graph-first / LLM-last</b>를 그대로 구현합니다. 순서는 이렇습니다.
          </p>
          <ol className="guide-steps">
            <li>
              <b>[지식설계]</b> 아는 것을 자연어 한 문장으로 입력합니다.
              <div className="guide-example guide-example-tight">
                “관심 단계는 남조류세포수가 1,000 cells/mL 이상일 때 발령된다.”
              </div>
            </li>
            <li>
              <b>Claude가 추출</b>해 미리보기로 보여줍니다.
              <div className="guide-example guide-example-tight">
                <Code>{"(남조류세포수:지표) , (관심)-[기준지표]->(남조류세포수)"}</Code>
              </div>
            </li>
            <li>
              여러분이 확인·수정하면 그래프에 <b>MERGE로 누적</b>됩니다. 같은 이름은 자동 병합돼{" "}
              <b>지식이 흩어지지 않습니다.</b>
            </li>
            <li>
              <b>표준 어휘 정규화</b>가 별칭을 표준어로 묶어 줍니다(= 온톨로지의 용어 통일).
            </li>
            <li>
              <b>[지식활용]</b> 자연어로 질문하면 <b>그래프가 답을 찾아</b> 줍니다(Text2Cypher). LLM은
              번역·표현만, 사실은 그래프가.
            </li>
          </ol>
          <p className="guide-p">
            여러분이 이 앱에서 문장으로 쌓는 것은 바로 그 <b>의미·관계 층(온톨로지의 뼈대)</b> —
            팔란티어가 사업화하고, ‘진짜 디지털 트윈’이 요구하는 바로 그 층입니다.
          </p>
          <div className="guide-callout guide-callout-final">
            한 줄 요약 — 여러분은 온톨로지 이론을 몰라도, <b>‘문장 쓰기’만으로 조직의 지식그래프(=디지털
            트윈의 뼈대)를 함께 만들고</b> 있습니다.
          </div>
        </section>

        <div className="guide-refs">
          <div className="guide-refs-title">
            더 깊이 알아보기 <span className="guide-refs-note">(새 창에서 열림)</span>
          </div>
          <ul>
            <li>
              <a
                className="guide-link"
                href="https://www.palantir.com/docs/foundry/ontology/overview"
                target="_blank"
                rel="noopener noreferrer"
              >
                Palantir Docs — Ontology overview (“a digital twin of the organization”)
              </a>
            </li>
            <li>
              <a
                className="guide-link"
                href="https://blog.palantir.com/connecting-ai-to-decisions-with-the-palantir-ontology-c73f7b0a1a72"
                target="_blank"
                rel="noopener noreferrer"
              >
                Palantir Blog — Connecting AI to Decisions with the Palantir Ontology
              </a>
            </li>
            <li>
              <a
                className="guide-link"
                href="https://blog.palantir.com/building-with-palantir-aip-data-tools-for-rag-oag-b3b509c8b0f3"
                target="_blank"
                rel="noopener noreferrer"
              >
                Palantir Blog — Data Tools for RAG/OAG (Ontology-Augmented Generation)
              </a>
            </li>
            <li>
              <a
                className="guide-link"
                href="https://www.tandfonline.com/doi/full/10.1080/00207543.2021.2014591"
                target="_blank"
                rel="noopener noreferrer"
              >
                Tao et al. — The emergence of cognitive digital twin (Int. J. of Production Research, 2021)
              </a>
            </li>
          </ul>
        </div>

        <p className="guide-source">
          이 자료는 사내 교육 <b>‘2026 마이크로디그리 – 빅데이터 분석(이채석, KAIST)’</b>의 그래프DB·
          온톨로지 강의를 토대로, 팔란티어 온톨로지·디지털 트윈에 대한 공개 자료를 더해 이 앱의 맥락으로
          재구성한 것입니다.
        </p>

        <div className="guide-foot-actions">
          <button type="button" className="primary" onClick={onBack}>
            돌아가기
          </button>
        </div>
      </article>
    </div>
  );
}
