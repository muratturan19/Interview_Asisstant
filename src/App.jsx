import { useEffect, useMemo, useState } from 'react';

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
            <td>{value?.score ?? '—'}</td>
            <td>{value?.max_score ?? '—'}</td>
            <td>{value?.weight ?? '—'}</td>
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
                {item.score} / {item.max_score}
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
  const [modes, setModes] = useState([]);
  const [modeError, setModeError] = useState('');
  const [selectedMode, setSelectedMode] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [remainingPairs, setRemainingPairs] = useState(null);
  const [history, setHistory] = useState([]);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [isLoadingQuestion, setIsLoadingQuestion] = useState(false);
  const [isSendingMessage, setIsSendingMessage] = useState(false);
  const [evaluationTranscript, setEvaluationTranscript] = useState('');
  const [evaluationTouched, setEvaluationTouched] = useState(false);
  const [evaluationResult, setEvaluationResult] = useState(null);
  const [evaluationError, setEvaluationError] = useState('');
  const [isEvaluating, setIsEvaluating] = useState(false);

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
          setModes(receivedModes);
          if (receivedModes.length && !selectedMode) {
            setSelectedMode(receivedModes[0].mode);
          }
        }
      } catch (err) {
        if (!cancelled) {
          setModeError(err.message || 'Mod listesi alınamadı');
        }
      }
    };

    fetchModes();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!evaluationTouched) {
      setEvaluationTranscript(formatHistoryForTranscript(history));
    }
  }, [history, evaluationTouched]);

  const selectedModeInfo = modes.find((mode) => mode.mode === selectedMode);

  const handleSelectMode = (event) => {
    const nextMode = event.target.value;
    setSelectedMode(nextMode);
    setCurrentQuestion(null);
    setHistory([]);
    setRemainingPairs(null);
    setEvaluationResult(null);
    setEvaluationTranscript('');
    setEvaluationTouched(false);
  };

  const handleStartInterview = async () => {
    if (!selectedMode) {
      setError('Lütfen bir mod seçin.');
      return;
    }
    setIsLoadingQuestion(true);
    setError('');
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
      setCurrentQuestion({
        prompt: data.question,
        part: data.part,
      });
      setRemainingPairs(data.remaining_pairs ?? null);
      setHistory([]);
      setEvaluationResult(null);
      setEvaluationTranscript('');
      setEvaluationTouched(false);
    } catch (err) {
      setError(err.message || 'İlk soru alınamadı.');
    } finally {
      setIsLoadingQuestion(false);
    }
  };

  const handleSendMessage = async (event) => {
    event.preventDefault();
    if (!selectedMode) {
      setError('Lütfen bir mod seçin.');
      return;
    }
    if (!apiKey.trim()) {
      setError('Anthropic API key gerekli.');
      return;
    }
    if (!message.trim()) {
      setError('Mesaj boş olamaz.');
      return;
    }

    setIsSendingMessage(true);
    setError('');
    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          mode: selectedMode,
          message: message.trim(),
          api_key: apiKey.trim(),
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.error || 'Mesaj gönderilemedi.');
      }
      setHistory(Array.isArray(data.history) ? data.history : []);
      setRemainingPairs(
        typeof data.remaining_pairs === 'number' ? data.remaining_pairs : null
      );
      setMessage('');
      if (data.limit_reached) {
        setError('Soru sınırına ulaşıldı. Değerlendirme yapabilirsiniz.');
      }
    } catch (err) {
      setError(err.message || 'Mesaj gönderilemedi.');
    } finally {
      setIsSendingMessage(false);
    }
  };

  const handleEvaluate = async () => {
    if (!selectedMode) {
      setEvaluationError('Lütfen bir mod seçin.');
      return;
    }
    if (!apiKey.trim()) {
      setEvaluationError('Anthropic API key gerekli.');
      return;
    }
    if (!evaluationTranscript.trim()) {
      setEvaluationError('Değerlendirilecek transcript boş olamaz.');
      return;
    }

    setIsEvaluating(true);
    setEvaluationError('');
    try {
      const response = await fetch('/api/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: apiKey.trim(),
          transcript: evaluationTranscript.trim(),
          evaluation_mode: selectedMode,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.error || 'Değerlendirme başarısız.');
      }
      setEvaluationResult(data);
      setEvaluationTouched(false);
    } catch (err) {
      setEvaluationError(err.message || 'Değerlendirme başarısız.');
    } finally {
      setIsEvaluating(false);
    }
  };

  const handleTranscriptChange = (event) => {
    setEvaluationTranscript(event.target.value);
    setEvaluationTouched(true);
  };

  return (
    <div className="page">
      <header>
        <h1>Interview Assistant</h1>
        <p className="subtitle">
          Mod seçimiyle ilk soruyu alın, sohbet edin ve transkripti değerlendirin.
        </p>
      </header>

      <main>
        <section className="card">
          <h2>1. Mod Seçimi</h2>
          {modeError && <p className="error">{modeError}</p>}
          <label className="field">
            <span>Değerlendirme modu</span>
            <select value={selectedMode} onChange={handleSelectMode}>
              <option value="" disabled>
                Bir mod seçin
              </option>
              {modes.map((mode) => (
                <option key={mode.mode} value={mode.mode}>
                  {mode.mode.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
          {selectedModeInfo && (
            <div className="mode-details">
              <p>{selectedModeInfo.description}</p>
              <CriteriaList criteria={selectedModeInfo.criteria} />
              <ScaleDetails scale={selectedModeInfo.scale} />
            </div>
          )}
        </section>

        <section className="card">
          <h2>2. API Anahtarı</h2>
          <label className="field">
            <span>Anthropic API Key</span>
            <input
              type="password"
              placeholder="sk-ant-..."
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              autoComplete="off"
            />
          </label>
        </section>

        <section className="card">
          <div className="section-header">
            <h2>3. Sohbet</h2>
            <button
              type="button"
              onClick={handleStartInterview}
              disabled={isLoadingQuestion || !selectedMode}
            >
              {isLoadingQuestion ? 'Yükleniyor...' : 'İlk Soruyu Al'}
            </button>
          </div>
          {error && <p className="error">{error}</p>}
          {currentQuestion && (
            <div className="question-card">
              <h3>{currentQuestion.part || 'Soru'}</h3>
              <p>{currentQuestion.prompt}</p>
              {typeof remainingPairs === 'number' && (
                <span className="remaining">Kalan soru hakkı: {remainingPairs}</span>
              )}
            </div>
          )}

          <form className="chat-form" onSubmit={handleSendMessage}>
            <textarea
              rows={4}
              placeholder="Yanıtınızı yazın..."
              value={message}
              onChange={(event) => setMessage(event.target.value)}
            />
            <button type="submit" disabled={isSendingMessage}>
              {isSendingMessage ? 'Gönderiliyor...' : 'Mesaj Gönder'}
            </button>
          </form>

          <HistoryView history={history} />
        </section>

        <section className="card">
          <div className="section-header">
            <h2>4. Değerlendirme</h2>
            <button
              type="button"
              onClick={() => {
                setEvaluationTranscript(formatHistoryForTranscript(history));
                setEvaluationTouched(false);
              }}
              disabled={!history.length}
            >
              Sohbeti Aktar
            </button>
          </div>
          {evaluationError && <p className="error">{evaluationError}</p>}
          <textarea
            rows={8}
            placeholder="Transkripti buraya yapıştırın veya Sohbeti Aktar ile otomatik doldurun."
            value={evaluationTranscript}
            onChange={handleTranscriptChange}
          />
          <button type="button" onClick={handleEvaluate} disabled={isEvaluating}>
            {isEvaluating ? 'Değerlendiriliyor...' : 'Değerlendir'}
          </button>

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
