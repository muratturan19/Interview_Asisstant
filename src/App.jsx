import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

const createSessionId = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const formatHistoryForTranscript = (history) =>
  history
    .map((entry) => {
      const speaker = entry.role === 'assistant' ? 'Assistant' : 'Candidate';
      return `${speaker}: ${entry.content}`;
    })
    .join('\n');

const MIC_STATE_COPY = {
  disabled: {
    label: 'Mikrofon Kapalı',
    hint: 'Asistan konuşurken mikrofon devre dışı.',
  },
  ready: {
    label: 'Mikrofon Hazır',
    hint: 'Cevabınızı kaydetmek için tıklayın.',
  },
  listening: {
    label: 'Dinleniyor... (Durdurmak için tekrar tıklayın)',
    hint: 'Yanıtınızı net ve doğal bir şekilde söyleyin.',
  },
  received: {
    label: 'Yanıt Alındı',
    hint: 'Asistan yeni soruyu hazırlıyor.',
  },
};

const CriteriaList = ({ criteria }) => {
  if (!criteria?.length) {
    return null;
  }

  return (
    <ul className="criteria-list">
      {criteria.map((criterion) => (
        <li key={criterion.name}>
          <strong>{criterion.name}</strong>
          <span>{criterion.description}</span>
        </li>
      ))}
    </ul>
  );
};

const ScaleDetails = ({ scale }) => {
  if (!scale?.levels?.length) {
    return null;
  }

  return (
    <div className="scale-card">
      <h4>{scale.label}</h4>
      <ul>
        {scale.levels.map((level) => (
          <li key={level.value}>
            <span className="scale-value">{level.value}</span>
            <span className="scale-description">{level.description}</span>
          </li>
        ))}
      </ul>
    </div>
  );
};

const HistoryView = ({ history }) => {
  if (!history.length) {
    return <p className="muted">Henüz sohbet başlatılmadı.</p>;
  }

  return (
    <ul className="history-list">
      {history.map((entry, index) => (
        <li key={`${entry.role}-${index}`} className={entry.role}>
          <span className="badge">{entry.role === 'assistant' ? 'Asistan' : 'Aday'}</span>
          <p>{entry.content}</p>
        </li>
      ))}
    </ul>
  );
};

const CriterionTable = ({ scores }) => {
  const entries = Object.entries(scores || {});
  if (!entries.length) {
    return null;
  }

  return (
    <table className="criterion-table">
      <thead>
        <tr>
          <th>Kriter</th>
          <th>Puan</th>
          <th>Maksimum</th>
          <th>Ağırlık</th>
        </tr>
      </thead>
      <tbody>
        {entries.map(([key, value]) => (
          <tr key={key}>
            <td>{key.replace(/_/g, ' ')}</td>
            <td>{value?.score ?? value?.band ?? value?.value ?? '—'}</td>
            <td>{value?.max_score ?? '—'}</td>
            <td>{value?.weight ? `${Math.round(value.weight * 100)}%` : '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
};

const BreakdownList = ({ breakdown }) => {
  if (!breakdown?.length) {
    return null;
  }

  return (
    <div className="breakdown-list">
      <h4>Soru Bazlı Sonuçlar</h4>
      <ul>
        {breakdown.map((item, index) => (
          <li key={item.question_number ?? index}>
            <div className="breakdown-header">
              <span>
                Soru {item.question_number ?? index + 1}{' '}
                {item.part ? `· ${item.part}` : ''}
              </span>
              <span>
                {item.score ?? item.band ?? '—'}
                {item.max_score ? ` / ${item.max_score}` : ''}
              </span>
            </div>
            <p>{item.feedback}</p>
          </li>
        ))}
      </ul>
    </div>
  );
};

const EquivalentScores = ({ equivalents }) => {
  const entries = Object.entries(equivalents || {});
  if (!entries.length) {
    return null;
  }

  return (
    <div className="equivalent-scores">
      <h4>Eşdeğer Skorlar</h4>
      <ul>
        {entries.map(([key, value]) => (
          <li key={key}>
            <strong>{key.replace(/_/g, ' ')}</strong>
            <span>{value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
};

const ExamplesList = ({ examples }) => {
  if (!examples) {
    return null;
  }

  const { good = [], needs_work: needsWork = [] } = examples;

  if (!good.length && !needsWork.length) {
    return null;
  }

  return (
    <div className="examples-card">
      {good.length > 0 && (
        <div>
          <h4>Güçlü Örnekler</h4>
          <ul>
            {good.map((item, index) => (
              <li key={`good-${index}`}>{item}</li>
            ))}
          </ul>
        </div>
      )}
      {needsWork.length > 0 && (
        <div>
          <h4>Gelişim Alanları</h4>
          <ul>
            {needsWork.map((item, index) => (
              <li key={`needs-${index}`}>{item}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

function App() {
  const sessionId = useMemo(createSessionId, []);
  const isClient = typeof window !== 'undefined';
  const [modes, setModes] = useState([]);
  const [modeError, setModeError] = useState('');
  const [selectedMode, setSelectedMode] = useState('');
  const [defaultMode, setDefaultMode] = useState('');
  const [evaluationModes, setEvaluationModes] = useState([]);

  const evaluationReady = useMemo(() => {
    if (!selectedMode) {
      return false;
    }
    return evaluationModes.includes(selectedMode);
  }, [evaluationModes, selectedMode]);

  const [apiKey, setApiKey] = useState('');
  const [apiKeyVisible, setApiKeyVisible] = useState(false);
  const [apiKeyStatus, setApiKeyStatus] = useState({ type: '', message: '' });
  const [hasStoredApiKey, setHasStoredApiKey] = useState(false);

  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [remainingPairs, setRemainingPairs] = useState(null);
  const [chatHistory, setChatHistory] = useState([]);
  const chatHistoryRef = useRef([]);
  const lastSpokenSignatureRef = useRef('');
  const updateChatHistory = useCallback((updater) => {
    setChatHistory((prev) => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      chatHistoryRef.current = next;
      if (!next.length) {
        lastSpokenSignatureRef.current = '';
      }
      return next;
    });
  }, []);

  const [error, setError] = useState('');
  const [isLoadingQuestion, setIsLoadingQuestion] = useState(false);
  const [interviewStatus, setInterviewStatus] = useState({ type: '', text: '' });
  const [micState, setMicState] = useState('disabled');
  const [isSpeechSupported, setIsSpeechSupported] = useState(() =>
    isClient ? null : true,
  );
  const [speechSupportChecked, setSpeechSupportChecked] = useState(() => !isClient);
  const [canSpeak, setCanSpeak] = useState(false);
  const canSpeakRef = useRef(false);
  const [interviewActive, setInterviewActive] = useState(false);
  const [interviewFinished, setInterviewFinished] = useState(false);

  const [evaluationResult, setEvaluationResult] = useState(null);
  const [evaluationError, setEvaluationError] = useState('');
  const [isEvaluating, setIsEvaluating] = useState(false);

  const recognitionRef = useRef(null);
  const listeningEnabledRef = useRef(false);
  const isListeningRef = useRef(false);
  const recognitionCapturedRef = useRef(false);
  const recognitionErrorRef = useRef(false);
  const microphonePermissionRef = useRef(false);
  const missingApiKey = useMemo(
    () => !hasStoredApiKey && !apiKey.trim(),
    [apiKey, hasStoredApiKey],
  );
  const speechEnabled = isSpeechSupported === true;

  const updateStatus = useCallback((type, text) => {
    setInterviewStatus({ type, text });
  }, []);

  const readyMicrophone = useCallback(
    (text = '🎤 Mikrofon hazır. Hazır olduğunuzda konuşmaya başlayın.') => {
      listeningEnabledRef.current = true;
      recognitionCapturedRef.current = false;
      recognitionErrorRef.current = false;
      setMicState('ready');
      updateStatus('', text);
    },
    [updateStatus]
  );

  const voicesLoadedRef = useRef(false);
  const voicesLoadingRef = useRef(null);

  const ensureVoices = useCallback(() => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
      return Promise.resolve();
    }

    if (voicesLoadedRef.current && window.speechSynthesis.getVoices().length > 0) {
      return Promise.resolve();
    }

    if (!voicesLoadingRef.current) {
      voicesLoadingRef.current = new Promise((resolve) => {
        const handleVoices = () => {
          voicesLoadedRef.current = true;
          window.speechSynthesis.removeEventListener('voiceschanged', handleVoices);
          resolve();
        };

        const existingVoices = window.speechSynthesis.getVoices();
        if (existingVoices.length > 0) {
          voicesLoadedRef.current = true;
          resolve();
          return;
        }

        window.speechSynthesis.addEventListener('voiceschanged', handleVoices);
        window.speechSynthesis.getVoices();

        setTimeout(() => {
          window.speechSynthesis.removeEventListener('voiceschanged', handleVoices);
          resolve();
        }, 1000);
      });
    }

    return voicesLoadingRef.current;
  }, []);

  const selectVoiceForText = useCallback((text) => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
      return null;
    }

    const voices = window.speechSynthesis.getVoices();
    if (!voices.length) {
      return null;
    }

    const hasTurkishChars = /[ğüşöçıİĞÜŞÖÇ]/i.test(text || '');
    const targetPrefix = hasTurkishChars ? 'tr' : 'en';
    return (
      voices.find((voice) => voice.lang?.toLowerCase().startsWith(targetPrefix)) ||
      voices.find((voice) => voice.default) ||
      voices[0]
    );
  }, []);

  const speakText = useCallback(
    (text) => {
      if (!text || !canSpeakRef.current || typeof window === 'undefined') {
        return Promise.resolve();
      }

      return ensureVoices().then(() => {
        return new Promise((resolve) => {
          const utterance = new window.SpeechSynthesisUtterance(text);
          const selectedVoice = selectVoiceForText(text);
          if (selectedVoice) {
            utterance.voice = selectedVoice;
            utterance.lang = selectedVoice.lang;
          } else {
            utterance.lang = /[ğüşöçıİĞÜŞÖÇ]/i.test(text) ? 'tr-TR' : 'en-US';
          }

          utterance.rate = 0.95;
          utterance.pitch = 1;
          utterance.onend = resolve;
          utterance.onerror = resolve;

          window.speechSynthesis.cancel();
          window.speechSynthesis.resume();
          window.speechSynthesis.speak(utterance);
        });
      });
    },
    [ensureVoices, selectVoiceForText],
  );

  const speakLatestAssistantMessage = useCallback(
    (historyOverride) => {
      if (!canSpeakRef.current) {
        return;
      }

      const historyToUse = historyOverride ?? chatHistoryRef.current;
      for (let index = historyToUse.length - 1; index >= 0; index -= 1) {
        const entry = historyToUse[index];
        if (entry.role !== 'assistant' || !entry.content) {
          continue;
        }

        const signature = `${index}:${entry.content}`;
        if (lastSpokenSignatureRef.current === signature) {
          return;
        }

        lastSpokenSignatureRef.current = signature;
        speakText(entry.content);
        return;
      }
    },
    [speakText],
  );

  const handleEvaluate = useCallback(
    async ({ transcriptOverride, autoTriggered = false } = {}) => {
      if (!selectedMode) {
        setEvaluationError('Lütfen bir mod seçin.');
        return false;
      }

      if (!evaluationReady) {
        setEvaluationError('Seçilen mod için otomatik değerlendirme desteklenmiyor.');
        return false;
      }

      const transcriptSource =
        transcriptOverride ?? formatHistoryForTranscript(chatHistoryRef.current);
      const transcript = transcriptSource.trim();

      if (!transcript) {
        setEvaluationError('Değerlendirilecek transcript boş olamaz.');
        return false;
      }

      const keyToSend = apiKey.trim();
      if (!hasStoredApiKey && !keyToSend) {
        setEvaluationError('Anthropic API key gerekli.');
        return false;
      }

      setIsEvaluating(true);
      setEvaluationError('');

      try {
        const payload = {
          transcript,
          evaluation_mode: selectedMode,
        };
        if (keyToSend) {
          payload.api_key = keyToSend;
        }

        const response = await fetch('/api/evaluate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data?.error || 'Değerlendirme başarısız.');
        }

        setEvaluationResult(data);
        if (data.mode) {
          setSelectedMode((prev) => prev || data.mode);
        }
        if (autoTriggered) {
          updateStatus('success', 'Değerlendirme tamamlandı.');
        }
        return true;
      } catch (err) {
        const messageText = err instanceof Error ? err.message : 'Değerlendirme başarısız.';
        setEvaluationError(messageText);
        if (autoTriggered) {
          updateStatus('error', messageText);
        }
        return false;
      } finally {
        setIsEvaluating(false);
      }
    },
    [apiKey, evaluationReady, hasStoredApiKey, selectedMode, updateStatus]
  );

  const finalizeInterview = useCallback(
    async (historyOverride) => {
      setInterviewActive(false);
      setInterviewFinished(true);
      listeningEnabledRef.current = false;
      setMicState('disabled');

      const historyToUse = historyOverride ?? chatHistoryRef.current;
      const transcript = formatHistoryForTranscript(historyToUse);
      updateStatus('info', '📤 Yanıtlar değerlendiriliyor...');
      await handleEvaluate({ transcriptOverride: transcript, autoTriggered: true });
    },
    [handleEvaluate, updateStatus]
  );

  const ensureMicrophone = useCallback(async () => {
    if (microphonePermissionRef.current || typeof navigator === 'undefined') {
      return;
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((track) => track.stop());
    microphonePermissionRef.current = true;
  }, []);

  const startListening = useCallback(async () => {
    const recognition = recognitionRef.current;
    if (!recognition || !listeningEnabledRef.current) {
      return;
    }

    try {
      if (!microphonePermissionRef.current) {
        await ensureMicrophone();
      }
      recognitionCapturedRef.current = false;
      recognitionErrorRef.current = false;
      isListeningRef.current = true;
      recognition.start();
      setMicState('listening');
      updateStatus('', '🎤 Dinliyorum... lütfen cevabınızı söyleyin.');
    } catch (err) {
      isListeningRef.current = false;
      setMicState('ready');
      const messageText = err instanceof Error ? err.message : 'Mikrofon başlatılamadı.';
      updateStatus('error', messageText);
    }
  }, [ensureMicrophone, updateStatus]);

  const sendMessageToChat = useCallback(
    async (rawMessage, { fromVoice = false } = {}) => {
      const text = rawMessage.trim();

      if (!interviewActive) {
        const msg = 'Lütfen önce mülakatı başlatın.';
        if (fromVoice) {
          updateStatus('error', msg);
        } else {
          setError(msg);
        }
        return false;
      }

      if (!selectedMode) {
        const msg = 'Lütfen bir mod seçin.';
        if (fromVoice) {
          updateStatus('error', msg);
        } else {
          setError(msg);
        }
        return false;
      }

      if (!text) {
        if (fromVoice) {
          updateStatus('error', 'Ses algılanamadı, tekrar deneyin.');
        } else {
          setError('Mesaj boş olamaz.');
        }
        return false;
      }

      const keyToSend = apiKey.trim();
      if (!hasStoredApiKey && !keyToSend) {
        const msg = 'Anthropic API key gerekli.';
        if (fromVoice) {
          updateStatus('error', msg);
        } else {
          setError(msg);
        }
        return false;
      }

      const pendingUserMessage = { role: 'user', content: text };
      const historyAfterUser = [...chatHistoryRef.current, pendingUserMessage];
      updateChatHistory(historyAfterUser);

      setError('');
      if (fromVoice) {
        updateStatus('', '🧠 Yanıt gönderiliyor...');
      }
      listeningEnabledRef.current = false;
      setMicState('disabled');

      try {
        const payload = {
          session_id: sessionId,
          mode: selectedMode,
          message: text,
        };
        if (keyToSend) {
          payload.api_key = keyToSend;
        }

        const response = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data?.error || 'Mesaj gönderilemedi.');
        }

        setRemainingPairs(
          typeof data.remaining_pairs === 'number' ? data.remaining_pairs : null
        );

        let fullHistory = historyAfterUser;
        if (data.reply) {
          const assistantMessage = { role: 'assistant', content: data.reply };
          fullHistory = [...historyAfterUser, assistantMessage];
          updateChatHistory(fullHistory);
          setCurrentQuestion({ prompt: data.reply });
          updateStatus('', '🔊 Asistan konuşuyor...');
          speakLatestAssistantMessage(fullHistory);
        }

        if (data.limit_reached || data.remaining_pairs === 0) {
          await finalizeInterview(fullHistory);
        } else if (speechEnabled) {
          readyMicrophone();
        } else {
          updateStatus(
            'error',
            'Tarayıcınız mikrofon desteği sunmuyor. Lütfen Chrome veya Edge kullanın.'
          );
        }

        return true;
      } catch (err) {
        const messageText = err instanceof Error ? err.message : 'Mesaj gönderilemedi.';
        if (fromVoice) {
          updateStatus('error', messageText);
          listeningEnabledRef.current = true;
          recognitionCapturedRef.current = false;
          recognitionErrorRef.current = false;
          setMicState('ready');
        } else {
          setError(messageText);
        }
        updateChatHistory((prev) => prev.slice(0, -1));
        return false;
      }
    },
    [
      apiKey,
      finalizeInterview,
      hasStoredApiKey,
      interviewActive,
      readyMicrophone,
      selectedMode,
      sessionId,
      speechEnabled,
      speakLatestAssistantMessage,
      updateChatHistory,
      updateStatus,
    ]
  );

  const handleStartInterview = useCallback(async () => {
    if (!speechEnabled) {
      updateStatus(
        'error',
        'Tarayıcınız mikrofon desteği sunmuyor. Lütfen Chrome veya Edge kullanın.',
      );
      return;
    }
    if (!selectedMode) {
      setError('Lütfen bir mod seçin.');
      return;
    }

    if (missingApiKey) {
      setError('Anthropic API key olmadan görüşme başlatılamaz.');
      setInterviewActive(false);
      return;
    }

    setIsLoadingQuestion(true);
    setError('');
    updateStatus('', '🎙️ Asistan ilk soruyu hazırlıyor...');
    setInterviewFinished(false);
    setEvaluationResult(null);
    setRemainingPairs(null);
    setCurrentQuestion(null);
    updateChatHistory([]);
    lastSpokenSignatureRef.current = '';
    listeningEnabledRef.current = false;
    setMicState('disabled');

    try {
      const response = await fetch('/api/get-first-question', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          mode: selectedMode,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.error || 'İlk soru alınamadı.');
      }

      setCurrentQuestion({ prompt: data.question, part: data.part });
      setRemainingPairs(data.remaining_pairs ?? null);
      const initialHistory = data.question
        ? [{ role: 'assistant', content: data.question }]
        : [];
      updateChatHistory(initialHistory);
      setInterviewActive(true);

      if (data.question) {
        updateStatus('', '🔊 Asistan konuşuyor...');
        speakLatestAssistantMessage(initialHistory);
      }

      if (speechEnabled) {
        readyMicrophone();
      }
    } catch (err) {
      const messageText = err instanceof Error ? err.message : 'İlk soru alınamadı.';
      setError(messageText);
      setInterviewActive(false);
      setMicState('disabled');
    } finally {
      setIsLoadingQuestion(false);
    }
  }, [
    missingApiKey,
    readyMicrophone,
    selectedMode,
    sessionId,
    speechEnabled,
    speakLatestAssistantMessage,
    updateChatHistory,
    updateStatus,
  ]);

  const handleMicButtonClick = useCallback(async () => {
    if (!speechEnabled) {
      return;
    }
    if (isListeningRef.current) {
      recognitionRef.current?.stop();
      return;
    }
    if (!listeningEnabledRef.current) {
      return;
    }
    await startListening();
  }, [speechEnabled, startListening]);

  const handleSelectMode = (event) => {
    const nextMode = event.target.value;
    setSelectedMode(nextMode);
    setCurrentQuestion(null);
    setRemainingPairs(null);
    updateChatHistory([]);
    setEvaluationResult(null);
    setInterviewActive(false);
    setInterviewFinished(false);
    setError('');
    updateStatus('info', 'Yeni mod seçildi. Mikrofonla yanıtlamak için mülakatı başlatın.');
  };

  const handleSaveApiKey = async () => {
    const keyToSave = apiKey.trim();
    if (!keyToSave) {
      setApiKeyStatus({ type: 'error', message: 'Lütfen bir Anthropic API anahtarı girin.' });
      return;
    }

    setApiKeyStatus({ type: '', message: 'Anahtar doğrulanıyor ve kaydediliyor...' });
    try {
      const response = await fetch('/api/save-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: keyToSave }),
      });
      const data = await response.json();
      if (!response.ok || !data.saved) {
        throw new Error(data?.error || 'API anahtarı kaydedilemedi.');
      }
      setApiKeyStatus({ type: 'success', message: 'API anahtarı başarıyla kaydedildi.' });
      setHasStoredApiKey(true);
    } catch (err) {
      const messageText = err instanceof Error ? err.message : 'API anahtarı kaydedilemedi.';
      setApiKeyStatus({ type: 'error', message: messageText });
    }
  };

  const micCopy = MIC_STATE_COPY[micState] || MIC_STATE_COPY.disabled;
  const micButtonDisabled =
    !speechEnabled ||
    !interviewActive ||
    interviewFinished ||
    (micState !== 'ready' && micState !== 'listening');

  const selectedModeInfo = modes.find((mode) => mode.mode === selectedMode);

  useEffect(() => {
    let cancelled = false;

    const fetchModes = async () => {
      try {
        setModeError('');
        const response = await fetch('/api/modes');
        if (!response.ok) {
          throw new Error('Mod listesi alınamadı');
        }
        const data = await response.json();
        if (!cancelled) {
          const receivedModes = data?.modes ?? [];
          const availableIds = new Set(receivedModes.map((mode) => mode.mode));

          const preferredFromResponse = data?.default_mode || '';
          const preferredMode = availableIds.has(preferredFromResponse)
            ? preferredFromResponse
            : receivedModes[0]?.mode ?? '';

          const evaluationList = receivedModes
            .filter((mode) => {
              if (Array.isArray(data?.evaluation_modes)) {
                return data.evaluation_modes.includes(mode.mode);
              }
              return Boolean(mode.evaluation_available);
            })
            .map((mode) => mode.mode);

          setModes(receivedModes);
          setDefaultMode(preferredMode);
          setEvaluationModes(evaluationList);
          setSelectedMode((prev) =>
            prev && availableIds.has(prev) ? prev : preferredMode
          );
        }
      } catch (err) {
        if (!cancelled) {
          const messageText = err instanceof Error ? err.message : 'Mod listesi alınamadı';
          setModeError(messageText);
        }
      }
    };

    fetchModes();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!modes.length) {
      return;
    }

    setSelectedMode((prev) => {
      if (prev && modes.some((mode) => mode.mode === prev)) {
        return prev;
      }
      return defaultMode || modes[0].mode;
    });
  }, [modes, defaultMode]);

  useEffect(() => {
    let cancelled = false;

    const checkStatus = async () => {
      try {
        const response = await fetch('/api/api-key-status');
        if (!response.ok) {
          throw new Error('API anahtarı durumu alınamadı.');
        }
        const data = await response.json();
        if (!cancelled) {
          setHasStoredApiKey(Boolean(data.has_key));
          if (data.default_mode) {
            setDefaultMode((prev) => prev || data.default_mode);
          }
          setSelectedMode((prev) => {
            if (prev) {
              return prev;
            }
            return data.last_mode || data.default_mode || prev;
          });
          if (data.has_key) {
            setApiKeyStatus({
              type: 'success',
              message: 'Sunucuda kayıtlı bir Anthropic API anahtarı bulundu.',
            });
          }
        }
      } catch (err) {
        if (!cancelled) {
          const messageText = err instanceof Error ? err.message : 'API anahtarı durumu alınamadı.';
          setApiKeyStatus({ type: 'error', message: messageText });
        }
      }
    };

    checkStatus();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }

    if ('speechSynthesis' in window) {
      setCanSpeak(true);
      canSpeakRef.current = true;
      ensureVoices();
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setIsSpeechSupported(false);
      setSpeechSupportChecked(true);
      return () => {
        window.speechSynthesis?.cancel();
      };
    }

    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    const handleResult = (event) => {
      recognitionCapturedRef.current = true;
      isListeningRef.current = false;

      const transcript = Array.from(event.results)
        .map((result) => result[0]?.transcript || '')
        .join(' ')
        .trim();

      recognition.stop();

      if (!transcript) {
        listeningEnabledRef.current = true;
        recognitionCapturedRef.current = false;
        setMicState('ready');
        updateStatus('error', 'Ses algılanamadı, tekrar deneyin.');
        return;
      }

      setMicState('received');
      updateStatus('', '🧠 Yanıt alındı. Asistan düşünüyor...');
      sendMessageToChat(transcript, { fromVoice: true });
    };

    const handleError = (event) => {
      recognitionErrorRef.current = true;
      isListeningRef.current = false;

      if (event.error === 'not-allowed') {
        listeningEnabledRef.current = false;
        setMicState('disabled');
        updateStatus('error', 'Mikrofon erişimi reddedildi. Tarayıcı izinlerini kontrol edin.');
        return;
      }

      if (event.error === 'no-speech') {
        listeningEnabledRef.current = true;
        recognitionCapturedRef.current = false;
        setMicState('ready');
        updateStatus('error', 'Ses algılanamadı, tekrar deneyin.');
        return;
      }

      listeningEnabledRef.current = true;
      recognitionCapturedRef.current = false;
      setMicState('ready');
      updateStatus('error', event.message || 'Ses tanıma sırasında bir hata oluştu.');
    };

    const handleEnd = () => {
      isListeningRef.current = false;
      if (recognitionCapturedRef.current || recognitionErrorRef.current) {
        return;
      }
      if (listeningEnabledRef.current) {
        setMicState('ready');
        updateStatus('error', 'Ses algılanamadı, tekrar deneyin.');
      }
    };

    recognition.addEventListener('result', handleResult);
    recognition.addEventListener('error', handleError);
    recognition.addEventListener('end', handleEnd);

    recognitionRef.current = recognition;
    setIsSpeechSupported(true);
    setSpeechSupportChecked(true);

    return () => {
      recognition.removeEventListener('result', handleResult);
      recognition.removeEventListener('error', handleError);
      recognition.removeEventListener('end', handleEnd);
      recognition.stop();
      window.speechSynthesis?.cancel();
    };
  }, [ensureVoices, sendMessageToChat, updateStatus]);

  useEffect(() => {
    if (!currentQuestion?.prompt) {
      return;
    }
    speakLatestAssistantMessage();
  }, [currentQuestion, speakLatestAssistantMessage]);

  useEffect(() => {
    speakLatestAssistantMessage(chatHistory);
  }, [chatHistory, speakLatestAssistantMessage]);

  useEffect(() => {
    if (canSpeak) {
      speakLatestAssistantMessage();
    }
  }, [canSpeak, speakLatestAssistantMessage]);

  const transcriptPreview = useMemo(
    () => formatHistoryForTranscript(chatHistory),
    [chatHistory],
  );

  const micHint = micCopy.hint;

  const pageHeader = (
    <header>
      <h1>Interview Assistant</h1>
      <p className="subtitle">
        Sesli mülakat başlatın, yanıtlarınızı mikrofonla kaydedin ve konuşmanızı değerlendirin.
      </p>
    </header>
  );

  if (speechSupportChecked && !speechEnabled) {
    return (
      <div className="page">
        {pageHeader}
        <main>
          <section className="card warning">
            <h2>Mikrofon Desteği Gerekiyor</h2>
            <p>
              Bu uygulama yalnızca Web Speech API desteği sunan tarayıcılarda çalışır. Lütfen
              Chrome veya Edge kullanın.
            </p>
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="page">
      {pageHeader}

      <main>
        <section className="card">
          <div className="section-header">
            <h2>1. Mod Seçimi</h2>
            {modes.length > 0 && (
              <span className="mode-count muted">{modes.length} mod hazır</span>
            )}
          </div>
          {modeError && <p className="error">{modeError}</p>}
          <label className="field">
            <span>Değerlendirme modu</span>
            <select value={selectedMode} onChange={handleSelectMode}>
              <option value="" disabled>
                Bir mod seçin
              </option>
              {modes.map((mode) => {
                const label = mode.title || mode.mode.toUpperCase();
                return (
                  <option key={mode.mode} value={mode.mode}>
                    {label}
                  </option>
                );
              })}
            </select>
          </label>
          {selectedModeInfo && (
            <div className="mode-details">
              <p>{selectedModeInfo.description}</p>
              <p className="muted">
                {selectedModeInfo.evaluation_available
                  ? 'Otomatik değerlendirme destekleniyor.'
                  : 'Bu mod şu an sadece soru pratiği sağlar.'}
              </p>
              <CriteriaList criteria={selectedModeInfo.criteria} />
              <ScaleDetails scale={selectedModeInfo.scale} />
            </div>
          )}
        </section>

        {!hasStoredApiKey && (
          <section className="card">
            <h2>2. API Anahtarı</h2>
            <label className="field">
              <span>Anthropic API Key</span>
              <div className="api-input-row">
                <input
                  type={apiKeyVisible ? 'text' : 'password'}
                  placeholder="sk-ant-..."
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  autoComplete="off"
                />
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setApiKeyVisible((prev) => !prev)}
                >
                  {apiKeyVisible ? 'Gizle' : 'Göster'}
                </button>
              </div>
            </label>
            <div className="api-actions">
              <button type="button" className="secondary" onClick={handleSaveApiKey}>
                API Anahtarını Kaydet
              </button>
            </div>
            {apiKeyStatus.message && (
              <p className={`status ${apiKeyStatus.type}`}>{apiKeyStatus.message}</p>
            )}
            {missingApiKey && (
              <p className="status error">
                Mülakatı başlatmak için geçerli bir Anthropic API anahtarı gereklidir.
              </p>
            )}
          </section>
        )}

        <section className="card">
          <div className="section-header">
            <h2>3. Sohbet</h2>
            <button
              type="button"
              onClick={handleStartInterview}
              disabled={
                isLoadingQuestion || !selectedMode || missingApiKey || !speechEnabled
              }
            >
              {isLoadingQuestion ? 'Yükleniyor...' : 'İlk Soruyu Al'}
            </button>
          </div>
          {hasStoredApiKey && (
            <p className={`status ${apiKeyStatus.type || 'info'}`}>
              {apiKeyStatus.message ||
                'Sunucuda kayıtlı bir Anthropic API anahtarı bulundu. Sorular bu anahtarla yürütülecek.'}
            </p>
          )}
          {error && <p className="error">{error}</p>}
          {interviewStatus.text && (
            <p className={`status ${interviewStatus.type}`}>{interviewStatus.text}</p>
          )}

          {currentQuestion && (
            <div className="question-card">
              <h3>{currentQuestion.part || 'Soru'}</h3>
              <p>{currentQuestion.prompt}</p>
              {typeof remainingPairs === 'number' && (
                <span className="remaining">Kalan soru hakkı: {remainingPairs}</span>
              )}
            </div>
          )}

          {speechEnabled ? (
            <div className="mic-controls">
              <button
                type="button"
                className={`mic-button ${micState === 'listening' ? 'listening' : ''}`}
                onClick={handleMicButtonClick}
                disabled={micButtonDisabled}
              >
                {micCopy.label}
              </button>
              <span className="mic-hint">{micHint}</span>
            </div>
          ) : (
            <p className="status info">Mikrofon yetenekleri kontrol ediliyor...</p>
          )}

          {speechEnabled && (
            <p className="status info">
              Mikrofon etkin. Yanıtınızı konuşarak iletin ve kayıt için mikrofon düğmesini
              kullanın.
            </p>
          )}

          <HistoryView history={chatHistory} />
        </section>

        <section className="card">
          <div className="section-header">
            <h2>4. Değerlendirme</h2>
          </div>
          {evaluationError && <p className="error">{evaluationError}</p>}
          <div className="transcript-preview">
            <h3>Otomatik Transcript</h3>
            {transcriptPreview ? (
              <pre>{transcriptPreview}</pre>
            ) : (
              <p className="muted">Transcript oluşturmak için önce sohbeti başlatın.</p>
            )}
          </div>
          <button
            type="button"
            onClick={() => handleEvaluate()}
            disabled={isEvaluating || !evaluationReady || !chatHistory.length}
          >
            {isEvaluating ? 'Değerlendiriliyor...' : 'Değerlendir'}
          </button>

          {!evaluationReady && selectedMode && (
            <p className="status info">
              Bu mod için değerlendirme yakında. Lütfen değerlendirme desteklenen bir mod seçin.
            </p>
          )}

          {evaluationResult && (
            <div className="evaluation-results">
              <h3>
                Sonuç · {evaluationResult.mode?.toUpperCase() || selectedMode.toUpperCase()}
              </h3>
              <p className="overall-score">
                Genel Puan: <strong>{evaluationResult.overall_score ?? '—'}</strong>{' '}
                <span className="scale">({evaluationResult.overall_scale || '—'})</span>
              </p>
              {evaluationResult.cefr_level && (
                <p className="cefr">CEFR Seviyesi: {evaluationResult.cefr_level}</p>
              )}

              <CriterionTable scores={evaluationResult.criterion_scores} />
              <BreakdownList breakdown={evaluationResult.question_breakdown} />

              {evaluationResult.strengths?.length > 0 && (
                <div className="pill-group">
                  <h4>Güçlü Yanlar</h4>
                  <ul>
                    {evaluationResult.strengths.map((item, index) => (
                      <li key={`strength-${index}`}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}

              {evaluationResult.improvements?.length > 0 && (
                <div className="pill-group warning">
                  <h4>Geliştirme Alanları</h4>
                  <ul>
                    {evaluationResult.improvements.map((item, index) => (
                      <li key={`improvement-${index}`}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}

              <EquivalentScores equivalents={evaluationResult.equivalent_scores} />
              <ExamplesList examples={evaluationResult.specific_examples} />

              {evaluationResult.detailed_feedback && (
                <div className="feedback-block">
                  <h4>Detaylı Geri Bildirim</h4>
                  <p>{evaluationResult.detailed_feedback}</p>
                </div>
              )}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
