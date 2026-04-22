import { useState } from "react";
import { Text, View, TextInput, Button, ScrollView } from "react-native";

export default function HomeScreen() {
  const [url, setUrl] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const analyzeSong = async () => {
    setLoading(true);
    setResult(null);

    try {
      const res = await fetch("http://192.168.1.8:8000/analyze-song-simple", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          youtube_url: url,
          job_mode: "analysis",
          instruments_to_suppress: ["guitar"],
        }),
      });

      const data = await res.json();
      setResult(data);
    } catch (err) {
      console.error(err);
      setResult({ error: "Something went wrong" });
    }

    setLoading(false);
  };

  return (
    <View style={{ flex: 1, padding: 20, paddingTop: 60 }}>
      <Text style={{ fontSize: 24, fontWeight: "bold", marginBottom: 20 }}>
        Song Analyzer 🎵
      </Text>

      <TextInput
        placeholder="Paste YouTube link"
        value={url}
        onChangeText={setUrl}
        style={{
          borderWidth: 1,
          padding: 10,
          marginBottom: 10,
          borderRadius: 5,
        }}
      />

      <Button title="Analyze" onPress={analyzeSong} />

      {loading && <Text style={{ marginTop: 20 }}>Analyzing...</Text>}

      {result && (
        <ScrollView style={{ marginTop: 20 }}>
          <Text>Key: {result.key}</Text>
          <Text style={{ marginTop: 10 }}>
          Progression: {result.progression_summary?.join(" → ")}</Text>
          <Text>BPM: {result.bpm}</Text>
          <Text>Time Signature: {result.time_signature}</Text>

          <Text style={{ marginTop: 10, fontWeight: "bold" }}>
            Chords:
          </Text>

          {result.chords?.slice(0, 10).map((c: any, i: number) => (
            <Text key={i}>
              {c.start_sec.toFixed(1)}s - {c.chord}
            </Text>
          ))}
        </ScrollView>
      )}
    </View>
  );
}