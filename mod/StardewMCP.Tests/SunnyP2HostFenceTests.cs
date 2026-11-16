using System;
using System.Collections.Concurrent;
using System.Linq;
using System.Threading.Tasks;
using StardewMCP.Agent;
using Xunit;

namespace StardewMCP.Tests;

/// <summary>
/// Pure .NET source tests against the dormant real-mod C# class.
/// This does not launch, authenticate or interrupt a real game process.
/// </summary>
public class SunnyP2HostFenceTests
{
    private static (SunnyP2HostFence Fence, string Token, SunnyP2HostFence.Lease Lease) Ready()
    {
        var fence = new SunnyP2HostFence();
        fence.HostSaveLoaded(p1Human: true, p2Ai: true, p2ExternalBrainNone: true);
        var token = fence.HostIssueCredential(SunnyP2HostFence.Grant.Control |
                                              SunnyP2HostFence.Grant.Observe);
        Assert.NotNull(token);
        var lease = fence.TryAcquire(token);
        Assert.NotNull(lease);
        return (fence, token!, lease!);
    }

    [Fact]
    public void StartsStoppedWithoutAnyCredentialOrOwner()
    {
        var fence = new SunnyP2HostFence();
        Assert.True(fence.Stopped);
        Assert.Null(fence.TryAcquire("test"));
        Assert.Null(fence.HostIssueCredential(SunnyP2HostFence.Grant.Control));
        Assert.False(fence.HostArmForOneOperation());
        Assert.False(fence.TryQueueMutation("test", null, "op"));
    }

    [Theory]
    [InlineData(false, true, true)]
    [InlineData(true, false, true)]
    [InlineData(true, true, false)]
    public void P1MustBeHumanAndP2MustBeExternalAi(bool p1, bool p2, bool external)
    {
        var fence = new SunnyP2HostFence();
        fence.HostSaveLoaded(p1, p2, external);
        Assert.Null(fence.HostIssueCredential(SunnyP2HostFence.Grant.Control));
        Assert.Null(fence.TryAcquire("test"));
        Assert.True(fence.Stopped);
    }

    [Fact]
    public void HostIssuesHighEntropyIndependentGameTokenAndOpaqueSession()
    {
        var (fence, token, lease) = Ready();
        Assert.Equal(43, token.Length);
        Assert.All(token, c => Assert.True((c >= 'A' && c <= 'Z') ||
                                          (c >= 'a' && c <= 'z') ||
                                          (c >= '0' && c <= '9') || c is '-' or '_'));
        Assert.NotEqual(token, lease.Session);
        Assert.Equal(43, lease.Epoch.Length);
        Assert.Equal(43, lease.Instance.Length);
        Assert.Null(fence.TryAcquire(token)); // no unreviewed owner takeover
        Assert.False(fence.TryQueueMutation(token + "x", lease, "op1"));
        Assert.False(fence.TryQueueMutation("external-model-key", lease, "op1"));
        Assert.False(fence.TryQueueMutation(token, lease, "op1")); // host STOP starts engaged
    }

    [Fact]
    public void ObserveOnlyGrantCannotObtainP2ControlLease()
    {
        var fence = new SunnyP2HostFence();
        fence.HostSaveLoaded(true, true, true);
        var token = fence.HostIssueCredential(SunnyP2HostFence.Grant.Observe);
        Assert.NotNull(token);
        Assert.Null(fence.TryAcquire(token));
        Assert.Null(fence.HostIssueCredential(SunnyP2HostFence.Grant.None));
        Assert.Null(fence.HostIssueCredential((SunnyP2HostFence.Grant)8));
        Assert.True(fence.Stopped);
    }

    [Fact]
    public void HostArmIsNotEquivalentToSendOrEffectAndOnlyOneMutationCanBeReserved()
    {
        var (fence, token, lease) = Ready();
        Assert.True(fence.HostArmForOneOperation());
        Assert.False(fence.Stopped);
        Assert.True(fence.TryQueueMutation(token, lease, "op1"));
        Assert.True(fence.PendingUnknown);
        Assert.False(fence.TryQueueMutation(token, lease, "op1"));
        Assert.False(fence.TryQueueMutation(token, lease, "op2"));
        Assert.False(fence.HostArmForOneOperation());
        Assert.True(fence.TryBeginOnGameThread(lease, "op1"));
        Assert.True(fence.MayContinueOnGameThread(lease, "op1"));
        fence.ToolReplyObserved("op1", isError: false);
        Assert.True(fence.PendingUnknown); // even successful ACK is not effect evidence
        Assert.False(fence.TryQueueMutation(token, lease, "op2"));
    }

    [Fact]
    public void StopAfterQueueFencesStartAndDoesNotErasePendingOperation()
    {
        var (fence, token, lease) = Ready();
        Assert.True(fence.HostArmForOneOperation());
        Assert.True(fence.TryQueueMutation(token, lease, "queue1"));
        var beforeStop = fence.StopRevision;
        fence.HostStop();
        Assert.True(fence.Stopped);
        Assert.True(fence.StopRevision > beforeStop);
        Assert.True(fence.PendingUnknown);
        Assert.False(fence.TryBeginOnGameThread(lease, "queue1"));
        Assert.False(fence.MayContinueOnGameThread(lease, "queue1"));
        Assert.False(fence.HostArmForOneOperation());
    }

    [Fact]
    public void StopDuringRunningFencesEveryLaterGameThreadStep()
    {
        var (fence, token, lease) = Ready();
        Assert.True(fence.HostArmForOneOperation());
        Assert.True(fence.TryQueueMutation(token, lease, "run1"));
        Assert.True(fence.TryBeginOnGameThread(lease, "run1"));
        fence.HostStop();
        Assert.False(fence.MayContinueOnGameThread(lease, "run1"));
        fence.ToolReplyObserved("run1", isError: false);
        Assert.True(fence.PendingUnknown);
        Assert.False(fence.HostArmForOneOperation());
    }

    [Fact]
    public void SaveReloadAndTitleRotateEpochAndCannotRevivePendingAction()
    {
        var (fence, token, lease) = Ready();
        Assert.True(fence.HostArmForOneOperation());
        Assert.True(fence.TryQueueMutation(token, lease, "sleep1"));
        fence.HostReturnedToTitle();
        Assert.True(fence.Stopped);
        Assert.True(fence.PendingUnknown);
        Assert.False(fence.TryBeginOnGameThread(lease, "sleep1"));
        fence.HostSaveLoaded(true, true, true);
        Assert.False(fence.TryBeginOnGameThread(lease, "sleep1"));
        Assert.False(fence.MayContinueOnGameThread(lease, "sleep1"));
        Assert.Null(fence.TryAcquire(token));
        Assert.Null(fence.HostIssueCredential(SunnyP2HostFence.Grant.Control));
        Assert.False(fence.HostArmForOneOperation());
    }

    [Fact]
    public void RoleChangeAndCredentialRotationInvalidateOldLeaseWithoutDispatch()
    {
        var (fence, oldToken, oldLease) = Ready();
        var newToken = fence.HostIssueCredential(SunnyP2HostFence.Grant.Control);
        Assert.NotNull(newToken);
        Assert.NotEqual(newToken, oldToken);
        Assert.Null(fence.TryAcquire(oldToken));
        var newLease = fence.TryAcquire(newToken);
        Assert.NotNull(newLease);
        Assert.NotEqual(newLease!.Session, oldLease.Session);
        Assert.True(fence.HostArmForOneOperation());
        Assert.False(fence.TryQueueMutation(oldToken, oldLease, "op1"));
        fence.HostRolesChanged(p1Human: false, p2Ai: true, p2ExternalBrainNone: true);
        Assert.True(fence.Stopped);
        Assert.False(fence.TryQueueMutation(newToken, newLease, "op1"));
        Assert.False(fence.MayContinueOnGameThread(newLease, "op1"));
        Assert.Null(fence.TryAcquire(newToken));
    }

    [Fact]
    public void ConcurrentStopAndBeginningCannotPermitNextStepAfterStopReturns()
    {
        var (fence, token, lease) = Ready();
        Assert.True(fence.HostArmForOneOperation());
        Assert.True(fence.TryQueueMutation(token, lease, "op"));
        var results = new ConcurrentBag<bool>();
        var first = Task.Run(() => results.Add(fence.TryBeginOnGameThread(lease, "op")));
        var second = Task.Run(() => fence.HostStop());
        Task.WaitAll(first, second);
        Assert.True(fence.Stopped);
        Assert.False(fence.MayContinueOnGameThread(lease, "op"));
        Assert.True(fence.PendingUnknown);
        Assert.True(results.Count == 1);
    }

    [Fact]
    public void NoOwnerOrSessionRevivalAfterHostStopAndNewSave()
    {
        var (fence, token, lease) = Ready();
        fence.HostStop();
        fence.HostSaveLoaded(true, true, true);
        var laterToken = fence.HostIssueCredential(SunnyP2HostFence.Grant.Control);
        Assert.NotNull(laterToken);
        Assert.NotEqual(token, laterToken);
        var laterLease = fence.TryAcquire(laterToken);
        Assert.NotNull(laterLease);
        Assert.NotEqual(lease.Epoch, laterLease!.Epoch);
        Assert.NotEqual(lease.Session, laterLease.Session);
        Assert.True(fence.HostArmForOneOperation());
        Assert.False(fence.TryQueueMutation(token, lease, "old"));
        Assert.True(fence.TryQueueMutation(laterToken, laterLease, "new"));
        Assert.False(fence.TryBeginOnGameThread(lease, "new"));
    }

    [Fact]
    public void ExplicitStopBeforeFirstMutationCannotBeRearmedInSameEpoch()
    {
        var (fence, token, lease) = Ready();
        fence.HostStop();
        Assert.True(fence.Stopped);
        Assert.False(fence.PendingUnknown);
        Assert.False(fence.HostArmForOneOperation());
        Assert.False(fence.TryQueueMutation(token, lease, "after-stop"));
        Assert.Null(fence.HostIssueCredential(SunnyP2HostFence.Grant.Control));
        // A future trusted new load can generate a fresh credential, never
        // revalidate the prior owner or re-use the prior credential.
        fence.HostSaveLoaded(true, true, true);
        var token2 = fence.HostIssueCredential(SunnyP2HostFence.Grant.Control);
        Assert.NotNull(token2);
        var lease2 = fence.TryAcquire(token2);
        Assert.NotNull(lease2);
        Assert.NotEqual(lease.Epoch, lease2!.Epoch);
        Assert.False(fence.TryQueueMutation(token, lease, "after-old-stop"));
    }

    [Fact]
    public void InvalidInitialRolesCannotBeRepairedWithinTheSameEpoch()
    {
        var fence = new SunnyP2HostFence();
        fence.HostSaveLoaded(false, true, true);
        fence.HostRolesChanged(true, true, true);
        Assert.Null(fence.HostIssueCredential(SunnyP2HostFence.Grant.Control));
        Assert.False(fence.HostArmForOneOperation());
        fence.HostSaveLoaded(true, true, true);
        Assert.NotNull(fence.HostIssueCredential(SunnyP2HostFence.Grant.Control));
    }

    [Fact]
    public void ValidRoleBecomingInvalidCanOnlyRecoverWithNewLoad()
    {
        var (fence, token, lease) = Ready();
        fence.HostRolesChanged(false, true, true);
        fence.HostRolesChanged(true, true, true);
        Assert.False(fence.HostArmForOneOperation());
        Assert.Null(fence.HostIssueCredential(SunnyP2HostFence.Grant.Control));
        Assert.False(fence.TryQueueMutation(token, lease, "stale"));
    }

}
