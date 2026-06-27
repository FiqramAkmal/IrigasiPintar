document.addEventListener('DOMContentLoaded', () => {
  const chartData = window.dashboardData;
  if (!chartData || !Array.isArray(chartData.labels)) {
    return;
  }

  const refreshIntervalMs = Number(chartData.refreshIntervalMs ?? 5000);
  const bannerVariants = ['good', 'warn', 'danger', 'info'];
  const controlApiUrl = chartData.apiUrl.replace('/status', '/control');
  const snapshotRefreshMs = Number(chartData.piSnapshotRefreshMs ?? 5000);
  let streamHeartbeatAt = 0;

  const nodes = {
    clock: document.getElementById('clockValue'),
    date: document.getElementById('dateValue'),
    forecastTemperature: document.getElementById('forecastTemperatureValue'),
    forecastPrecipitation: document.getElementById('forecastPrecipitationValue'),
    forecastTime: document.getElementById('forecastTimeValue'),
    temperature: document.getElementById('temperatureValue'),
    temperatureGauge: document.getElementById('temperatureGauge'),
    temperatureGaugeValue: document.getElementById('temperatureGaugeValue'),
    temperatureInsight: document.getElementById('temperatureInsight'),
    soil: document.getElementById('soilValue'),
    soilBarFill: document.getElementById('soilBarFill'),
    soilGaugeValue: document.getElementById('soilGaugeValue'),
    soilInsight: document.getElementById('soilInsight'),
    humidity: document.getElementById('humidityValue'),
    humidityFill: document.getElementById('humidityFill'),
    humidityGaugeValue: document.getElementById('humidityGaugeValue'),
    humidityInsight: document.getElementById('humidityInsight'),
    statusBanner: document.getElementById('statusBanner'),
    wateringMessage: document.getElementById('wateringMessage'),
    prediction: document.getElementById('predictionValue'),
    command: document.getElementById('commandValue'),
    weatherTableBody: document.getElementById('weatherTableBody'),
    controlPanel: document.getElementById('controlPanel'),
    liveBadge: document.getElementById('liveBadge'),
    liveBadgeText: document.getElementById('liveBadgeText'),
    controlStateLabel: document.getElementById('controlStateLabel'),
    controlRoleLabel: document.getElementById('controlRoleLabel'),
    manualDefaultLabel: document.getElementById('manualDefaultLabel'),
    effectiveCommandLabel: document.getElementById('effectiveCommandLabel'),
    controlHelpText: document.getElementById('controlHelpText'),
    modeAutoButton: document.getElementById('modeAutoButton'),
    modeManualButton: document.getElementById('modeManualButton'),
    manualOnButton: document.getElementById('manualOnButton'),
    manualOffButton: document.getElementById('manualOffButton'),
    streamFrame: document.getElementById('streamFrame'),
    detectionFrame: document.getElementById('detectionFrame'),
    streamStatusBadge: document.getElementById('streamStatusBadge'),
    detectionStatusBadge: document.getElementById('detectionStatusBadge'),
    diseaseCondition: document.getElementById('diseaseConditionValue'),
    diseaseConfidence: document.getElementById('diseaseConfidenceValue'),
    diseaseStatus: document.getElementById('diseaseStatusValue'),
    diseaseDetectedAt: document.getElementById('diseaseDetectedAtValue'),
  };

  const formatNumber = (value, suffix = '') => `${Number(value ?? 0).toFixed(2).replace(/\.00$/, '')}${suffix}`;
  const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

  const describeTemperature = (value) => {
    if (value >= 32) return 'Udara cukup panas, pantau intensitas panas.';
    if (value <= 20) return 'Udara lebih sejuk dari biasanya.';
    return 'Suhu berada pada rentang yang relatif stabil.';
  };

  const describeHumidity = (value) => {
    if (value >= 80) return 'Kelembapan tinggi, udara terasa lebih basah.';
    if (value <= 40) return 'Kelembapan rendah, kondisi udara cenderung kering.';
    return 'Kelembapan udara berada di level nyaman.';
  };

  const describeSoil = (value) => {
    if (value >= 70) return 'Tanah basah dan cadangan air masih tinggi.';
    if (value <= 25) return 'Tanah mulai kering, perlu perhatian lebih.';
    return 'Kelembapan tanah masih cukup aman.';
  };

  const updateRealtimeVisuals = (sensor) => {
    const temperature = Number(sensor.temperature ?? 0);
    const humidity = Number(sensor.humidity ?? 0);
    const soil = Number(sensor.soil ?? 0);

    const temperatureRatio = clamp((temperature + 10) / 50, 0, 1);
    const humidityRatio = clamp(humidity / 100, 0, 1);
    const soilRatio = clamp(soil / 100, 0, 1);

    if (nodes.temperatureGauge) {
      nodes.temperatureGauge.style.setProperty('--gauge-value', `${temperatureRatio}`);
      nodes.temperatureGauge.dataset.value = `${Math.round(temperatureRatio * 100)}`;
    }
    if (nodes.temperatureGaugeValue) {
      nodes.temperatureGaugeValue.textContent = formatNumber(temperature, '°C');
    }
    if (nodes.temperatureInsight) {
      nodes.temperatureInsight.textContent = describeTemperature(temperature);
    }

    if (nodes.humidityFill) {
      const humidityPercent = `${Math.round(humidityRatio * 100)}%`;
      nodes.humidityFill.style.height = humidityPercent;
      nodes.humidityFill.style.minHeight = '14%';
      nodes.humidityFill.dataset.value = humidityPercent;
    }
    if (nodes.humidityGaugeValue) {
      nodes.humidityGaugeValue.textContent = formatNumber(humidity, '%');
    }
    if (nodes.humidityInsight) {
      nodes.humidityInsight.textContent = describeHumidity(humidity);
    }

    if (nodes.soilBarFill) {
      const soilPercent = `${Math.round(soilRatio * 100)}%`;
      nodes.soilBarFill.style.width = soilPercent;
      nodes.soilBarFill.dataset.value = soilPercent;
    }
    if (nodes.soilGaugeValue) {
      nodes.soilGaugeValue.textContent = formatNumber(soil, '%');
    }
    if (nodes.soilInsight) {
      nodes.soilInsight.textContent = describeSoil(soil);
    }
  };

  const renderRows = (rows) => {
    if (!nodes.weatherTableBody || !Array.isArray(rows)) {
      return;
    }

    nodes.weatherTableBody.innerHTML = rows.map((row) => `
      <tr>
        <td>${row.date_label}</td>
        <td>${row.temperature_2m}</td>
        <td>${row.humidity}</td>
        <td>${row.precipitation_probability}</td>
        <td>${row.precipitation}</td>
      </tr>
    `).join('');
  };

  const updateSensorStatus = (sensorStatus) => {
    if (!sensorStatus) {
      return;
    }

    if (nodes.liveBadge) {
      nodes.liveBadge.classList.remove('live', 'offline');
      nodes.liveBadge.classList.add(sensorStatus.state ?? 'offline');
    }

    if (nodes.liveBadgeText) {
      nodes.liveBadgeText.textContent = sensorStatus.label ?? 'Offline';
    }
  };

  const updateDiseaseTelemetry = (disease) => {
    if (!disease) {
      return;
    }

    if (nodes.diseaseCondition) {
      nodes.diseaseCondition.textContent = disease.kondisi_daun ?? '-';
    }
    if (nodes.diseaseConfidence) {
      nodes.diseaseConfidence.textContent = `${Number(disease.tingkat_keyakinan ?? 0).toFixed(2).replace(/\.00$/, '')}%`;
    }
    if (nodes.diseaseStatus) {
      nodes.diseaseStatus.textContent = disease.status_deteksi ?? '-';
    }
    if (nodes.diseaseDetectedAt) {
      nodes.diseaseDetectedAt.textContent = disease.detected_at ?? '-';
    }
  };

  const setVisionBadgeState = (node, isLive) => {
    if (!node) {
      return;
    }

    node.classList.remove('live', 'offline');
    node.classList.add(isLive ? 'live' : 'offline');
    node.textContent = isLive ? 'Live' : 'Offline';
  };

  const markStreamLive = () => {
    streamHeartbeatAt = Date.now();
    setVisionBadgeState(nodes.streamStatusBadge, true);
  };

  const monitorStreamHeartbeat = () => {
    if (!nodes.streamFrame) {
      return;
    }

    if (streamHeartbeatAt && Date.now() - streamHeartbeatAt <= 15000) {
      setVisionBadgeState(nodes.streamStatusBadge, true);
      return;
    }

    const looksLoaded = nodes.streamFrame.complete && nodes.streamFrame.naturalWidth > 0;
    setVisionBadgeState(nodes.streamStatusBadge, looksLoaded);
  };

  const refreshDetectionSnapshot = () => {
    if (!nodes.detectionFrame || !chartData.piDetectionImageUrl) {
      return;
    }

    const separator = chartData.piDetectionImageUrl.includes('?') ? '&' : '?';
    nodes.detectionFrame.src = `${chartData.piDetectionImageUrl}${separator}t=${Date.now()}`;
  };

  const updateControlPanel = (payload) => {
    const role = payload.current_role ?? chartData.currentRole ?? 'user';
    const controlState = payload.control_state ?? chartData.controlState;
    if (!controlState) {
      return;
    }

    const isAdmin = role === 'admin';
    const isManual = controlState.mode === 'manual';

    if (nodes.controlRoleLabel) nodes.controlRoleLabel.textContent = String(role).toUpperCase();
    if (nodes.controlStateLabel) nodes.controlStateLabel.textContent = String(controlState.mode ?? '-').toUpperCase();
    if (nodes.manualDefaultLabel) nodes.manualDefaultLabel.textContent = String(controlState.manual_command ?? '-').toUpperCase();
    if (nodes.effectiveCommandLabel) nodes.effectiveCommandLabel.textContent = String(controlState.last_effective_command ?? '-').toUpperCase();

    if (nodes.modeAutoButton) {
      nodes.modeAutoButton.disabled = !isAdmin;
      nodes.modeAutoButton.classList.toggle('active', controlState.mode === 'auto');
    }
    if (nodes.modeManualButton) {
      nodes.modeManualButton.disabled = !isAdmin;
      nodes.modeManualButton.classList.toggle('active', controlState.mode === 'manual');
    }
    if (nodes.manualOnButton) {
      nodes.manualOnButton.disabled = !isAdmin || !isManual;
      nodes.manualOnButton.classList.toggle('active', isManual && controlState.manual_command === 'on');
    }
    if (nodes.manualOffButton) {
      nodes.manualOffButton.disabled = !isAdmin || !isManual;
      nodes.manualOffButton.classList.toggle('active', isManual && controlState.manual_command === 'off');
    }

    if (nodes.controlHelpText) {
      if (!isAdmin) {
        nodes.controlHelpText.textContent = 'Monitoring Only!';
      } else if (!isManual) {
        nodes.controlHelpText.textContent = 'Mode auto aktif. Ubah ke manual dulu sebelum tombol ON/OFF bisa dipakai.';
      } else {
        nodes.controlHelpText.textContent = 'Mode manual aktif. Command ON/OFF akan dikirim langsung ke perangkat.';
      }
    }
  };

  const postControl = async (payload) => {
    const response = await fetch(controlApiUrl, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      credentials: 'same-origin',
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      return null;
    }

    return response.json();
  };

  const updateHeader = (generatedAt) => {
    if (!generatedAt) {
      return;
    }

    const date = new Date(generatedAt);
    if (Number.isNaN(date.getTime())) {
      return;
    }

    if (nodes.clock) {
      nodes.clock.textContent = `🕒 ${date.toLocaleTimeString('id-ID', { hour12: false })}`;
    }

    if (nodes.date) {
      nodes.date.textContent = date.toLocaleDateString('id-ID');
    }
  };

  const createLineChart = (elementId, datasetLabel, data, color, fill = false) => {
    const canvas = document.getElementById(elementId);
    if (!canvas) {
      return null;
    }

    return new Chart(canvas, {
      type: 'line',
      data: {
        labels: chartData.labels,
        datasets: [{
          label: datasetLabel,
          data,
          borderColor: color,
          backgroundColor: fill ? `${color}33` : color,
          fill,
          tension: 0.35,
          pointRadius: 2,
          pointHoverRadius: 3,
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        normalized: true,
        interaction: {
          intersect: false,
          mode: 'index',
        },
        scales: {
          x: {
            ticks: { color: '#afbdd3' },
            grid: { color: 'rgba(255,255,255,0.06)' },
          },
          y: {
            ticks: { color: '#afbdd3' },
            grid: { color: 'rgba(255,255,255,0.06)' },
          },
        },
        plugins: {
          legend: {
            labels: { color: '#f4f7fb' },
          },
        },
      },
    });
  };

  const temperatureChart = createLineChart('temperatureChart', 'Temperature (°C)', chartData.temperatureSeries, '#4fc3f7');
  const rainChart = createLineChart('rainChart', 'Precipitation Probability (%)', chartData.precipitationProbabilitySeries, '#78e08f', true);

  const applyPayload = (payload) => {
    if (!payload) {
      return;
    }

    updateHeader(payload.generated_at);
    updateSensorStatus(payload.sensor_status);
    updateDiseaseTelemetry(payload.disease);

    if (payload.forecast_summary) {
      if (nodes.forecastTemperature) nodes.forecastTemperature.textContent = formatNumber(payload.forecast_summary.temperature, '°C');
      if (nodes.forecastPrecipitation) nodes.forecastPrecipitation.textContent = formatNumber(payload.forecast_summary.precipitation_probability, '%');
      if (nodes.forecastTime) nodes.forecastTime.textContent = payload.forecast_summary.time_label ?? '-';
    }

    if (payload.sensor) {
      updateRealtimeVisuals(payload.sensor);
    }

    if (payload.watering && nodes.statusBanner) {
      nodes.statusBanner.classList.remove(...bannerVariants);
      if (payload.watering.variant) {
        nodes.statusBanner.classList.add(payload.watering.variant);
      }
      if (nodes.wateringMessage) nodes.wateringMessage.textContent = payload.watering.message ?? '-';
      if (nodes.command) nodes.command.textContent = String(payload.watering.command ?? '-').toUpperCase();
    }

    if (nodes.prediction) {
      nodes.prediction.textContent = payload.prediction ?? '-';
    }

    updateControlPanel(payload);

    if (Array.isArray(payload.weather_rows)) {
      renderRows(payload.weather_rows);
    }

    if (temperatureChart && Array.isArray(payload.weather_labels) && Array.isArray(payload.temperature_series)) {
      temperatureChart.data.labels = payload.weather_labels;
      temperatureChart.data.datasets[0].data = payload.temperature_series;
      temperatureChart.update('none');
    }

    if (rainChart && Array.isArray(payload.weather_labels) && Array.isArray(payload.precipitation_probability_series)) {
      rainChart.data.labels = payload.weather_labels;
      rainChart.data.datasets[0].data = payload.precipitation_probability_series;
      rainChart.update('none');
    }
  };

  const fetchStatus = async () => {
    try {
      const response = await fetch(chartData.apiUrl, {
        headers: { 'Accept': 'application/json' },
        cache: 'no-store',
      });

      if (!response.ok) {
        return;
      }

      const payload = await response.json();
      if (payload.error) {
        return;
      }

      applyPayload(payload);
    } catch (_error) {
    }
  };

  applyPayload({
    generated_at: chartData.generatedAt,
    current_role: chartData.currentRole,
    sensor_status: chartData.sensorStatus,
    control_state: chartData.controlState,
    sensor: chartData.sensor,
    forecast_summary: chartData.forecastSummary,
    disease: chartData.disease,
    prediction: chartData.prediction,
    watering: chartData.watering,
    weather_rows: chartData.weatherRows,
    weather_labels: chartData.labels,
    temperature_series: chartData.temperatureSeries,
    precipitation_probability_series: chartData.precipitationProbabilitySeries,
  });

  updateRealtimeVisuals(chartData.sensor);

  if (nodes.streamFrame) {
    nodes.streamFrame.addEventListener('load', markStreamLive);
    nodes.streamFrame.addEventListener('error', () => setVisionBadgeState(nodes.streamStatusBadge, false));
    if (nodes.streamFrame.complete && nodes.streamFrame.naturalWidth > 0) {
      markStreamLive();
    }
    window.setInterval(monitorStreamHeartbeat, 3000);
  }

  if (nodes.detectionFrame) {
    nodes.detectionFrame.addEventListener('load', () => setVisionBadgeState(nodes.detectionStatusBadge, true));
    nodes.detectionFrame.addEventListener('error', () => setVisionBadgeState(nodes.detectionStatusBadge, false));
    window.setInterval(refreshDetectionSnapshot, snapshotRefreshMs);
  }

  if (nodes.modeAutoButton) {
    nodes.modeAutoButton.addEventListener('click', async () => {
      const result = await postControl({ mode: 'auto' });
      if (result?.control_state) {
        applyPayload({ current_role: chartData.currentRole, control_state: result.control_state });
        await fetchStatus();
      }
    });
  }

  if (nodes.modeManualButton) {
    nodes.modeManualButton.addEventListener('click', async () => {
      const result = await postControl({ mode: 'manual' });
      if (result?.control_state) {
        applyPayload({ current_role: chartData.currentRole, control_state: result.control_state });
      }
    });
  }

  if (nodes.manualOnButton) {
    nodes.manualOnButton.addEventListener('click', async () => {
      const result = await postControl({ manual_command: 'on' });
      if (result?.control_state) {
        applyPayload({ current_role: chartData.currentRole, control_state: result.control_state });
        await fetchStatus();
      }
    });
  }

  if (nodes.manualOffButton) {
    nodes.manualOffButton.addEventListener('click', async () => {
      const result = await postControl({ manual_command: 'off' });
      if (result?.control_state) {
        applyPayload({ current_role: chartData.currentRole, control_state: result.control_state });
        await fetchStatus();
      }
    });
  }

  window.setInterval(fetchStatus, refreshIntervalMs);
});
