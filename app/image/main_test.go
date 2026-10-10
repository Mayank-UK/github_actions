package main

// Offline tests: the shared httpClient's transport is swapped for a fake
// RoundTripper, so no request ever leaves the process.

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
)

type roundTripperFunc func(*http.Request) (*http.Response, error)

func (f roundTripperFunc) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }

func useTransport(t *testing.T, rt http.RoundTripper) {
	t.Helper()
	original := httpClient.Transport
	httpClient.Transport = rt
	t.Cleanup(func() { httpClient.Transport = original })
}

func jsonResponse(status int, body string) *http.Response {
	return &http.Response{
		StatusCode: status,
		Header:     http.Header{"Content-Type": []string{"application/json"}},
		Body:       io.NopCloser(bytes.NewBufferString(body)),
	}
}

func decode(t *testing.T, res *httptest.ResponseRecorder) map[string]any {
	t.Helper()
	var m map[string]any
	if err := json.Unmarshal(res.Body.Bytes(), &m); err != nil {
		t.Fatalf("response is not valid JSON: %v (body=%q)", err, res.Body.String())
	}
	return m
}

func TestHealthZ(t *testing.T) {
	for _, path := range []string{"/health", "/healthz"} {
		rec := httptest.NewRecorder()
		healthHandler(rec, httptest.NewRequest(http.MethodGet, path, nil))
		if rec.Code != http.StatusOK {
			t.Fatalf("%s: status = %d, want 200", path, rec.Code)
		}
		if got := decode(t, rec); got["status"] != "ok" {
			t.Fatalf("%s: body = %v, want status ok", path, got)
		}
	}
}

func TestImageRequiresTopic(t *testing.T) {
	rec := httptest.NewRecorder()
	imageHandler(rec, httptest.NewRequest(http.MethodGet, "/image", nil))
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400", rec.Code)
	}
	if got := decode(t, rec); got["error"] != "topic is required" {
		t.Fatalf("body = %v, want error topic is required", got)
	}
}

func TestImagePicksLowestIndexWithImageInfo(t *testing.T) {
	// The more relevant page (index 1) has no imageinfo; the handler must
	// skip it and return index 2. Map order in the JSON is irrelevant.
	useTransport(t, roundTripperFunc(func(r *http.Request) (*http.Response, error) {
		if r.URL.Host != "commons.wikimedia.org" {
			t.Errorf("request went to %s, want commons.wikimedia.org", r.URL.Host)
		}
		if got := r.URL.Query().Get("gsrsearch"); got != "filetype:bitmap|drawing octopus" {
			t.Errorf("gsrsearch = %q, want topic appended", got)
		}
		return jsonResponse(200, `{"query":{"pages":{
			"200": {"index":2,"title":"File:Second.jpg","imageinfo":[{"url":"https://upload.example/second.jpg"}]},
			"100": {"index":1,"title":"File:First.jpg"}
		}}}`), nil
	}))

	rec := httptest.NewRecorder()
	imageHandler(rec, httptest.NewRequest(http.MethodGet, "/image?topic=octopus", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (body=%s)", rec.Code, rec.Body.String())
	}
	got := decode(t, rec)
	if got["imageUrl"] != "https://upload.example/second.jpg" {
		t.Fatalf("imageUrl = %v, want the index-2 result", got["imageUrl"])
	}
	if got["pageTitle"] != "File:Second.jpg" {
		t.Fatalf("pageTitle = %v, want File:Second.jpg", got["pageTitle"])
	}
	if got["topic"] != "octopus" {
		t.Fatalf("topic = %v, want octopus", got["topic"])
	}
}

func TestImageNoUsableResultsIsNulls(t *testing.T) {
	useTransport(t, roundTripperFunc(func(*http.Request) (*http.Response, error) {
		return jsonResponse(200, `{"query":{"pages":{
			"100": {"index":1,"title":"File:Empty.jpg"}
		}}}`), nil
	}))

	rec := httptest.NewRecorder()
	imageHandler(rec, httptest.NewRequest(http.MethodGet, "/image?topic=zzz", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 even on a miss", rec.Code)
	}
	got := decode(t, rec)
	if v, present := got["imageUrl"]; !present || v != nil {
		t.Fatalf("imageUrl = %v (present=%v), want JSON null", v, present)
	}
	if v, present := got["pageTitle"]; !present || v != nil {
		t.Fatalf("pageTitle = %v (present=%v), want JSON null", v, present)
	}
}

func TestImageUpstreamErrorDegradesToNulls(t *testing.T) {
	useTransport(t, roundTripperFunc(func(*http.Request) (*http.Response, error) {
		return jsonResponse(500, `{"error":"boom"}`), nil
	}))

	rec := httptest.NewRecorder()
	imageHandler(rec, httptest.NewRequest(http.MethodGet, "/image?topic=octopus", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (upstream failure must not 5xx)", rec.Code)
	}
	got := decode(t, rec)
	if v, present := got["imageUrl"]; !present || v != nil {
		t.Fatalf("imageUrl = %v (present=%v), want JSON null", v, present)
	}
}
